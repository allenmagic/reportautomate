import pandas as pd
import requests
import time
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, date
from pathlib import Path  # 导入 Path
from app.utils.logger import logger
from app.core.config import settings

router = APIRouter()


class EntityInput(BaseModel):
    """输入实体模型"""
    entity_code: str = Field(..., description="实体代码")
    entity_name: str = Field(..., description="实体名称")


class EntityOutput(BaseModel):
    """输出实体模型"""
    entity_code: str = Field(..., description="实体代码")
    entity_name: str = Field(..., description="实体名称")
    giin: str = Field(..., description="GIIN值")


class GIINSearchRequest(BaseModel):
    """GIIN查询请求模型"""
    entities: List[EntityInput] = Field(..., description="实体列表")


class GIINSearchResponse(BaseModel):
    """GIIN查询响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: List[EntityOutput] = Field(default=[], description="返回数据")
    processed_count: int = Field(..., description="处理的实体数量")
    download_time_seconds: float = Field(..., description="CSV下载耗时（秒）")
    processing_time_seconds: float = Field(..., description="数据处理耗时（秒）")
    file_status: str = Field(..., description="文件状态：downloaded/cached")
    timestamp: datetime = Field(default_factory=datetime.now, description="处理时间")


class GIINService:
    def __init__(self):
        self.csv_url = "https://apps.irs.gov/app/fatcaFfiList/data/FFIListFull.csv"
        # 【优化 1】使用 pathlib 构建路径，并添加类型提示
        self.csv_path: Path = settings.TEMP_DIR / "giin" / "FFIListFull.csv"
        self.giin_data: Optional[pd.DataFrame] = None

    def check_file_exists_and_current(self) -> bool:
        """
        检查CSV文件是否存在且是当天创建的
        返回: True表示文件存在且是当天的，False表示需要重新下载
        """
        try:
            # 【优化 2】使用 Path.exists() 方法
            if not self.csv_path.exists():
                logger.info(f"CSV文件不存在: {self.csv_path}")
                return False

            # 【优化 3】使用 Path.stat().st_mtime 获取修改时间
            file_mtime = self.csv_path.stat().st_mtime
            file_date = datetime.fromtimestamp(file_mtime).date()
            today = date.today()

            logger.info(f"CSV文件存在，文件日期: {file_date}, 今天: {today}")

            if file_date == today:
                logger.info(f"CSV文件是今天的，无需重新下载")
                return True
            else:
                logger.info(f"CSV文件不是今天的（文件日期: {file_date}），需要重新下载")
                return False

        except Exception as e:
            logger.error(f"检查文件状态失败: {e}")
            return False

    async def download_csv_file(self) -> tuple[bool, float]:
        """
        从指定URL下载CSV文件并保存到本地
        返回: (是否成功, 下载耗时)
        """
        start_time = time.time()

        try:
            # 【优化 4】使用 Path.parent.mkdir() 创建父目录
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"开始下载CSV文件从: {self.csv_url}")
            logger.info(f"注意：CSV文件较大，预计需要等待1-3分钟...")

            response = requests.get(self.csv_url, timeout=300, stream=True)
            response.raise_for_status()

            total_size = response.headers.get('content-length')
            if total_size:
                total_size = int(total_size)
                logger.info(f"文件大小: {total_size / (1024 * 1024):.2f} MB")

            downloaded_size = 0
            chunk_size = 8192

            # 【优化 5】使用 Path.open() 方法打开文件
            with self.csv_path.open('wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if downloaded_size % (10 * 1024 * 1024) == 0:
                            progress_info = f"已下载: {downloaded_size / (1024 * 1024):.2f} MB"
                            if total_size:
                                progress = (downloaded_size / total_size) * 100
                                progress_info = f"下载进度: {progress:.1f}% ({progress_info})"
                            logger.info(progress_info)

            download_time = time.time() - start_time
            logger.info(f"CSV文件下载完成，耗时: {download_time:.2f}秒")
            logger.info(f"文件已保存到: {self.csv_path}")

            return True, download_time

        except requests.Timeout as e:
            download_time = time.time() - start_time
            logger.error(f"下载CSV文件超时: {e}，耗时: {download_time:.2f}秒")
            return False, download_time
        except requests.RequestException as e:
            download_time = time.time() - start_time
            logger.error(f"下载CSV文件失败: {e}，耗时: {download_time:.2f}秒")
            return False, download_time
        except Exception as e:
            download_time = time.time() - start_time
            logger.error(f"保存CSV文件失败: {e}，耗时: {download_time:.2f}秒")
            return False, download_time

    def load_csv_data(self) -> bool:
        """读取CSV文件数据"""
        try:
            # 【优化 6】Path.exists() 再次使用
            if not self.csv_path.exists():
                logger.error(f"CSV文件不存在: {self.csv_path}")
                return False

            logger.info(f"开始读取CSV文件...")

            # pandas可以直接接受Path对象，无需修改
            self.giin_data = pd.read_csv(self.csv_path, encoding='utf-8', low_memory=False)
            logger.info(f"成功读取CSV文件，共{len(self.giin_data)}条记录")

            if 'FINm' not in self.giin_data.columns or 'GIIN' not in self.giin_data.columns:
                logger.error(f"CSV文件中缺少必要的列: FINm 或 GIIN")
                logger.info(f"可用列: {list(self.giin_data.columns)}")
                return False

            original_count = len(self.giin_data)
            self.giin_data = self.giin_data.dropna(subset=['FINm', 'GIIN'])
            cleaned_count = len(self.giin_data)

            if original_count != cleaned_count:
                logger.info(f"清理空值后，有效记录数: {cleaned_count} (原始: {original_count})")

            return True

        except Exception as e:
            logger.error(f"读取CSV文件失败: {e}")
            return False

    def find_giin_by_entity_name(self, entity_name: str) -> str:
        """根据entity_name在FINm字段中查找对应的GIIN值"""
        if self.giin_data is None:
            return ""
        try:
            matches = self.giin_data[
                self.giin_data['FINm'].str.contains(entity_name, case=False, na=False)
            ]
            if not matches.empty:
                giin_value = matches.iloc[0]['GIIN']
                logger.debug(f"找到匹配: {entity_name} -> {giin_value}")
                return str(giin_value) if pd.notna(giin_value) else ""
            else:
                logger.debug(f"未找到匹配: {entity_name}")
            return ""
        except Exception as e:
            logger.error(f"查找GIIN失败: {e}")
            return ""

    async def process_entities(self, entities: List[EntityInput]) -> tuple[List[EntityOutput], float]:
        """处理实体列表，为每个实体查找对应的GIIN值"""
        start_time = time.time()
        result = []
        logger.info(f"开始处理{len(entities)}个实体...")
        for i, entity in enumerate(entities, 1):
            giin_value = self.find_giin_by_entity_name(entity.entity_name)
            processed_entity = EntityOutput(
                entity_code=entity.entity_code,
                entity_name=entity.entity_name,
                giin=giin_value
            )
            result.append(processed_entity)
            if i % 100 == 0 or i == len(entities):
                logger.info(f"处理进度: {i}/{len(entities)} ({(i / len(entities) * 100):.1f}%)")
        processing_time = time.time() - start_time
        logger.info(f"实体处理完成，耗时: {processing_time:.2f}秒")
        return result, processing_time


# 创建服务实例
giin_service = GIINService()


@router.post("/giin_search", response_model=GIINSearchResponse)
async def search_giin(request: GIINSearchRequest, background_tasks: BackgroundTasks):
    """
    根据实体名称查询对应的GIIN值
    ... (docstring无变化) ...
    """
    try:
        logger.info(f"收到GIIN查询请求，实体数量: {len(request.entities)}")
        logger.info(f"步骤1: 检查GIIN数据文件状态...")
        file_is_current = giin_service.check_file_exists_and_current()
        download_time = 0.0
        file_status = "cached"
        if not file_is_current:
            logger.info(f"需要下载最新的GIIN数据文件...")
            download_success, download_time = await giin_service.download_csv_file()
            file_status = "downloaded"
            if not download_success:
                raise HTTPException(
                    status_code=500,
                    detail=f"下载CSV文件失败，请稍后重试。下载耗时: {download_time:.2f}秒"
                )
        else:
            logger.info(f"使用当天的缓存文件，跳过下载步骤")
        logger.info(f"步骤2: 加载GIIN数据...")
        if not giin_service.load_csv_data():
            raise HTTPException(status_code=500, detail="读取CSV文件失败")
        logger.info(f"步骤3: 查找GIIN值...")
        result, processing_time = await giin_service.process_entities(request.entities)
        logger.info(f"GIIN查询处理完成，返回{len(result)}条记录")
        if file_status == "downloaded":
            logger.info(
                f"总耗时: 下载{download_time:.2f}秒 + 处理{processing_time:.2f}秒 = {download_time + processing_time:.2f}秒")
        else:
            logger.info(f"总耗时: 处理{processing_time:.2f}秒（使用缓存文件）")
        return GIINSearchResponse(
            success=True,
            message="处理成功",
            data=result,
            processed_count=len(result),
            download_time_seconds=download_time,
            processing_time_seconds=processing_time,
            file_status=file_status
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
