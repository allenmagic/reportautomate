from fastapi import APIRouter
from app.api import endpoints
import importlib
import pkgutil  # Python 内置模块，无需安装

api_router = APIRouter()

# 自动发现并注册所有 endpoints 模块中的 router
for _, module_name, _ in pkgutil.iter_modules(endpoints.__path__):
    module = importlib.import_module(f"app.api.endpoints.{module_name}")

    if hasattr(module, 'router'):
        api_router.include_router(module.router, tags=[module_name])

__all__ = ["api_router"]
