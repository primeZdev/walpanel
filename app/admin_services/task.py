from app.admin_services.api import panels_api
from app.oprations.panel import panel_operations
from app.oprations.admin import admin_operations
from app.schema._input import CreateUserInput, UpdateUserInput
from app.log.logger_config import logger
from fastapi.responses import JSONResponse
from fastapi import status
from datetime import datetime
from uuid import uuid4
import json
import string
import secrets


class Task:
    def get_sublinks(self, db, username):
        try:
            admin = admin_operations.get_admin_data(db, username)
            panel = panel_operations.panel_data(db, admin.panel_id)
            return {"result": f"https://{panel.sub}/"}
        except Exception as e:
            logger.error(f"Error getting sublinks: {e}")
            return JSONResponse(
                content={"error": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def check_admin_traffic(self, db, username, _traffic):
        try:
            admin = admin_operations.get_admin_data(db, username)

            if admin.traffic < _traffic:
                return False

            return True
        except Exception as e:
            return False

    def reduce_admin_traffic(self, db, username, _traffic):
        try:
            admin_operations.reduce_traffic(db, username, _traffic)
        except Exception as e:
            return False

    def get_users(self, db, username):
        client_list = []

        try:
            admin = admin_operations.get_admin_data(db, username)
            panel = panel_operations.panel_data(db, admin.panel_id)

            result = panels_api.show_users(
                panel.url, panel.username, panel.password, admin.inbound_id
            )
            if not result or "obj" not in result or "settings" not in result["obj"]:
                logger.error("Result or settings not found in panel response")
                panels_api.login_with_out_savekey(
                    panel.url, panel.username, panel.password
                )
                self.get_users(db, username)  # Retry

            settings_str = result["obj"]["settings"]
            if not settings_str:
                logger.error("Settings string is empty")
                return {"clients": [], "error": "Settings data is empty"}

            try:
                settings_json = json.loads(settings_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return {"clients": [], "error": "Invalid settings JSON from panel"}

            clients = settings_json.get("clients", [])

            clients_status = panels_api.user_status(panel.url)
            online_emails = clients_status.get("obj") or []

            for c in clients:
                try:
                    client_obj = panels_api.user_obj(panel.url, c["email"])
                    upload = client_obj["obj"].get("up", 0)
                    download = client_obj["obj"].get("down", 0)
                    total_usage = (upload + download) / (1024**3)

                    client_list.append(
                        {
                            "email": c["email"],
                            "online": c["email"] in online_emails,
                            "id": c["id"],
                            "totalGB": c["totalGB"] / (1024**3),
                            "totalUsage": total_usage,
                            "expiryTime": datetime.fromtimestamp(
                                c["expiryTime"] / 1000
                            ).strftime("%Y-%m-%d"),
                            "enable": c["enable"],
                            "subId": c["subId"],
                        }
                    )
                except Exception as client_error:
                    logger.warning(
                        f"Failed to process client {c['email']}: {client_error}"
                    )

            return {"clients": client_list}

        except Exception as e:
            logger.error(f"Error fetching user list: {e}")
            panels_api.login_with_out_savekey(
                panel.url, panel.username, panel.password
            )
            return {
                "clients": client_list,
                "error": "Failed to fetch user list, try again.",
            }
        
    async def total_users_in_inbound(self, db, username: str) -> int:
        try:
            client_count = 0
            admin = admin_operations.get_admin_data(db, username)
            panel = panel_operations.panel_data(db, admin.panel_id)
            result = panels_api.show_users(
                panel.url, panel.username, panel.password, admin.inbound_id
            )
            if not result or "obj" not in result or "settings" not in result["obj"]:
                logger.error("Result or settings not found in panel response")
                panels_api.login_with_out_savekey(
                    panel.url, panel.username, panel.password
                )
                self.user_list(db, username)
            
            settings_str = result["obj"]["settings"]
            settings_json = json.loads(settings_str)
            clients = settings_json.get("clients", [])
            for c in clients:
                client_count += 1
            return client_count

        except Exception as e:
            logger.error(f"Error fetching user list: {e}")
            return {"error": "Failed to fetch user list, try again."}

    def create_user(self, db, username: str, request: CreateUserInput):
        if not self.check_admin_traffic(db, username, request.totalGB):
            return JSONResponse(
                content={"error": "Traffic limit reached"},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        try:
            data = admin_operations.get_admin_data(db, username)
            panel = panel_operations.panel_data(db, data.panel_id)

            _uuid = str(uuid4())
            subid = generate_secure_random_text(16)

            result = panels_api.add_user(
                panel.url,
                panel.username,
                panel.password,
                data.inbound_id,
                _uuid,
                subid,
                request.email,
                int(request.totalGB * (1024**3)),
                request.expiryTime,
                request.flow
            )

            if result["success"] is True:
                self.reduce_admin_traffic(db, username, request.totalGB)

            return JSONResponse(
                content={"result": result}, status_code=status.HTTP_201_CREATED
            )
        except Exception as e:
            return JSONResponse(
                content={"error": f"Create user failed: {str(e)}"},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete_client(self, db, username: str, user_id: str):
        try:
            admin = admin_operations.get_admin_data(db, username)
            panel = panel_operations.panel_data(db, admin.panel_id)

            result = panels_api.delete_client(
                panel.url,
                panel.username,
                panel.password,
                admin.inbound_id,
                user_id,
            )

            return JSONResponse(content=result.json(), status_code=status.HTTP_200_OK)
        except Exception as e:
            return JSONResponse(
                content={"error": f"Delete client failed: {str(e)}"},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update_client(self, db, username: str, user_id: str, request: UpdateUserInput):
        if not self.check_admin_traffic(db, username, request.totalGB):
            return JSONResponse(
                content={"error": "Traffic limit reached"},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        try:
            admin = admin_operations.get_admin_data(db, username)
            panel = panel_operations.panel_data(db, admin.panel_id)

            updated_client = {
                "id": user_id,
                "email": request.email,
                "totalGB": int(request.totalGB * (1024**3)),
                "expiryTime": request.expiryTime,
                "enable": True,
                "flow": "",
                "limitIp": 0,
                "tgId": "",
                "subId": request.subid,
                "comment": "",
                "reset": "",
            }

            result = panels_api.update_client(
                panel.url,
                panel.username,
                panel.password,
                admin.inbound_id,
                user_id,
                updated_client,
            )

            if result.status_code == 200:
                self.reduce_admin_traffic(db, username, request.totalGB)
                panels_api.reset_traffic(
                    panel.url,
                    panel.username,
                    panel.password,
                    admin.inbound_id,
                    request.email,
                )

            return JSONResponse(content=result.json(), status_code=status.HTTP_200_OK)
        except Exception as e:
            return JSONResponse(
                content={"error": f"Update client failed: {str(e)}"},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def reset_client_traffic(self, db, username: str, email: str):
        admin = admin_operations.get_admin_data(db, username)
        panel = panel_operations.panel_data(db, admin.panel_id)
        client = panels_api.user_obj(panel.url, email)
        _traffic = int(client["obj"]["total"] / (1024 ** 3))

        if not self.check_admin_traffic(db, username, _traffic):
            return JSONResponse(
                content={"error": "Traffic limit reached"},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        try:
            result = panels_api.reset_traffic(
                panel.url,
                panel.username,
                panel.password,
                admin.inbound_id,
                email,
            )

            if result.status_code == 200:
                self.reduce_admin_traffic(db, username, _traffic)

            return JSONResponse(content=result.json(), status_code=status.HTTP_200_OK)
        except Exception as e:
            return JSONResponse(
                content={"error": f"Reset traffic failed: {str(e)}"},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


admin_task = Task()


def generate_secure_random_text(length=16):
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))
