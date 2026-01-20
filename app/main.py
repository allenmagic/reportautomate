from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.core.security import verify_api_auth
from app.core.api_docs import API_HELP_CONTENT
from app.api.endpoints import (
    unzip,
    sharepoint,
    process_attachment,
    download,
    process_hsbc_daily_cash,
    process_citi_monthly_statement,
    process_hsbc_monthly_statement,
    render_pdf_doc,
    giin_search,
    process_citi_daily_balance,
    process_csb_daily_balance,
    generate_account_file,
)

# 创建FastAPI应用实例
app = FastAPI(
    title="文件解压服务",
    description="支持文件解压缩、PDF密码移除、文档渲染、银行数据处理等多种功能",
    version="1.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置模板目录
templates = Jinja2Templates(directory="app/templates")

# 设置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由配置列表
ROUTERS = [
    unzip,
    sharepoint,
    process_attachment,
    download,
    process_hsbc_daily_cash,
    process_citi_monthly_statement,
    process_hsbc_monthly_statement,
    render_pdf_doc,  # 包含 render_pdf_doc 和 render_typst_pdf 两个接口
    giin_search,
    process_citi_daily_balance,
    process_csb_daily_balance,
    generate_account_file,
]

# 批量注册路由
for router_module in ROUTERS:
    app.include_router(
        router_module.router, prefix="/api", dependencies=[Depends(verify_api_auth)]
    )


# 健康检查接口
@app.get("/", tags=["health"])
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "service": "file-processing-service",
        "version": app.version,
        "environment": settings.ENVIRONMENT,
        "features": [
            "文件解压",
            "PDF密码移除",
            "文档渲染(LaTeX/Typst)",
            "银行数据处理",
            "GIIN搜索",
            "PDF转Markdown",
        ],
    }


# API使用说明
@app.get("/api/help", tags=["help"])
async def api_help():
    """获取API使用说明"""
    return API_HELP_CONTENT


# 调试路由 - 查看所有注册的路由
@app.get("/debug/routes", tags=["debug"])
async def debug_routes():
    """查看所有注册的路由（仅用于调试）"""
    routes = []
    for route in app.routes:
        route_info = {
            "path": route.path,
            "name": route.name,
            "methods": list(route.methods)
            if hasattr(route, "methods") and route.methods
            else [],
        }
        routes.append(route_info)

    return {"total_routes": len(routes), "routes": routes}


# 应用启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化操作"""
    print(f"🚀 应用启动: {app.title} v{app.version}")
    print(f"📝 环境: {settings.ENVIRONMENT}")
    print(f"📚 API文档: http://localhost:8000/docs")
    print(f"❓ API帮助: http://localhost:8000/api/help")

    # 初始化Typst渲染器（如果需要）
    try:
        from app.api.endpoints.render_pdf_doc import init_typst_renderer

        init_typst_renderer()
        print("✅ Typst渲染器初始化成功")
    except Exception as e:
        print(f"⚠️  Typst渲染器初始化失败: {e}")


# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理操作"""
    print("👋 应用关闭")
    # 这里可以添加清理临时文件等操作


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    import traceback

    error_detail = {
        "error": str(exc),
        "type": type(exc).__name__,
        "path": request.url.path,
        "method": request.method,
    }

    # 在开发环境下返回详细的堆栈信息
    if settings.ENVIRONMENT == "development":
        error_detail["traceback"] = traceback.format_exc()

    return {"success": False, "message": "服务器内部错误", "detail": error_detail}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式下启用热重载
        log_level="info",
    )
