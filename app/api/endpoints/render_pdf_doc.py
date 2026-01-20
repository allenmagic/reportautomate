import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from datetime import date, time
from app.utils.logger import logger
from app.utils.jinja2_template_loader import elatex, load_template
from app.core.config import settings
import subprocess
import json
import typst

router = APIRouter()


class RenderFormRequest(BaseModel):
    task_id: str # 文档生成的任务ID
    file_name: Optional[str] = None # 生成文档的名称，非必须
    record_id: Optional[str] = None # 文档相关的记录ID，非必须
    template_name: str # 模板文件名，不带后缀
    data: dict # 生成PDF文件需要的数据

class RenderPDFResponse(BaseModel):
    task_id: str # 文档生成的任务ID
    record_id: Optional[str] = None # 文档相关的记录ID，非必须
    pdf: str # 生成PDF文件的路径


class TypstRenderer:
    def __init__(self, template_dir: str):
        """初始化 Typst 渲染器"""
        self.template_dir = Path(template_dir).resolve()
        logger.info(f"模板文件的绝对路径: {self.template_dir}")

        logger.info(f"TypstRenderer 初始化，模板目录: {self.template_dir}")

        if not self.template_dir.exists():
            logger.warning(f"模板目录不存在，正在创建: {self.template_dir}")
            self.template_dir.mkdir(parents=True, exist_ok=True)

        self._list_available_templates()

    def _list_available_templates(self):
        """列出所有可用的 Typst 模板"""
        try:
            templates = list(self.template_dir.glob("*.typ"))
            if templates:
                logger.info(f"找到 {len(templates)} 个 Typst 模板:")
                for t in templates:
                    logger.info(f"  - {t.name}")
            else:
                logger.warning(f"未找到任何 Typst 模板")
        except Exception as e:
            logger.error(f"列出模板失败: {e}")

    def render_to_pdf(self, template_name: str, data: dict, output_path: Path):
        """渲染 Typst 模板为 PDF"""
        template_name = template_name.replace('.typ', '')
        template_file = self.template_dir / f"{template_name}.typ"
        logger.debug(f"模板文件路径: {template_file}")

        if not template_file.exists():
            logger.error(f"模板文件不存在: {template_file}")
            available = [t.stem for t in self.template_dir.glob("*.typ")]
            if available:
                logger.error(f"可用模板: {', '.join(available)}")
            raise FileNotFoundError(f"模板文件不存在: {template_name}.typ")

        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 1. 准备 sys_inputs 字典
            sys_inputs = {
                "data": json.dumps(data, ensure_ascii=False)
            }

            # 2. 直接编译并写入目标文件。当提供了 `output` 参数时，`typst.compile` 函数会直接操作文件，
            typst.compile(input=template_file,output=output_path,sys_inputs=sys_inputs)

            # 3. 确认文件已生成且内容不为空。
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError("Typst 编译过程未报错，但输出的 PDF 文件丢失或为空。")

            logger.info(f"✅ 编译成功，PDF 已保存至: {output_path}")

        except subprocess.CalledProcessError as e:
            error_details = e.stderr.strip()
            logger.error(f"Typst 编译失败:\n--- Typst Error ---\n{error_details}\n-------------------")
            raise RuntimeError(f"Typst 编译失败: {error_details}")

        except FileNotFoundError:
            error_msg = "Typst 程序未找到. 请确保其已经正确安装并被使用."
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        except Exception as e:
            logger.error(f"渲染过程中发生未知错误: {e}", exc_info=True)
            raise


# 全局渲染器实例
renderer = None


def init_typst_renderer():
    """初始化 Typst 渲染器"""
    global renderer

    try:

        logger.info("初始化 Typst 渲染器...")

        # 检查 Typst
        result = subprocess.run(
            ["typst", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        logger.info(f"Typst 版本: {result.stdout.strip()}")

        # ✅ 从配置读取模板根目录，拼接 typst 子目录
        typst_dir = Path(settings.TEMPLATE_DIR) / "typst"

        logger.info(f"模板根目录: {settings.TEMPLATE_DIR}")
        logger.info(f"Typst 子目录: {typst_dir}")

        # ✅ 传递完整路径
        renderer = TypstRenderer(template_dir=str(typst_dir))

        logger.info("Typst 渲染器初始化成功")
        return renderer

    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        renderer = None
        return None


# 自动初始化
try:
    init_typst_renderer()
except Exception as e:
    logger.warning(f"自动初始化 TypstRenderer 失败: {e}")


@router.post("/render_typst_pdf", response_model=RenderPDFResponse, tags=["render"])
async def render_typst_pdf(request: RenderFormRequest):
    """使用 Typst 引擎生成 PDF"""
    logger.info(f"收到 Typst 渲染请求: task_id={request.task_id}, template={request.template_name}")

    # 检查渲染器
    if renderer is None:
        logger.error("Typst 渲染器未初始化")
        raise HTTPException(status_code=500, detail="Typst 渲染器未初始化")

    try:
        from app.core.config import settings

        # 创建任务目录
        task_dir = Path(settings.TEMP_DIR) / request.task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"任务目录: {task_dir}")

        # 生成文件名
        if request.file_name:
            pdf_filename = request.file_name if request.file_name.endswith('.pdf') else f"{request.file_name}.pdf"
        else:
            pdf_filename = f"{request.task_id}.pdf"

        pdf_file = task_dir / pdf_filename
        logger.info(f"开始渲染 PDF: {pdf_file}")

        # 执行渲染（模板名称不需要包含路径，TypstRenderer 会自动在 typst/ 子目录查找）
        renderer.render_to_pdf(
            template_name=request.template_name,  # ✅ 直接使用 "payment_request"
            data=request.data,
            output_path=pdf_file
        )

        # 验证文件生成
        if not pdf_file.exists():
            logger.error(f"PDF 文件未生成: {pdf_file}")
            raise RuntimeError("PDF 文件生成失败")

        file_size = pdf_file.stat().st_size
        logger.info(f"PDF 文件已生成: {pdf_file}, 大小: {file_size} bytes")

        # 检查文件是否为空
        if file_size == 0:
            logger.error("生成的 PDF 文件为空")
            raise RuntimeError("生成的 PDF 文件为空，请检查模板内容")

        return RenderPDFResponse(
            task_id=request.task_id,
            record_id=request.record_id,
            pdf=str(pdf_file)
        )

    except FileNotFoundError as e:
        logger.error(f"文件不存在错误: {e}")
        raise HTTPException(status_code=404, detail=f"文件不存在: {str(e)}")

    except RuntimeError as e:
        logger.error(f"渲染运行时错误: {e}")
        raise HTTPException(status_code=500, detail=f"渲染失败: {str(e)}")

    except Exception as e:
        logger.error(f"生成 PDF 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成 PDF 文件失败: {str(e)}")