import os
import logging
from typing import Union, Optional
from pathlib import Path
import tos
from app.utils.logger import setup_logger

logger = setup_logger("tos_client")


class TOSClient:
    def __init__(self):
        self.access_key = os.getenv("VOLC_AK")
        self.secret_key = os.getenv("VOLC_SK")
        self.endpoint = os.getenv("TOS_ENDPOINT")
        self.region = os.getenv("TOS_REGION")
        self.bucket = os.getenv("TOS_BUCKET")

        if not all(
            [self.access_key, self.secret_key, self.endpoint, self.region, self.bucket]
        ):
            raise ValueError("TOS配置信息不完整，请检查环境变量")

        try:
            self.client = tos.TosClientV2(
                self.access_key, self.secret_key, self.endpoint, self.region
            )
            logger.info("TOS客户端初始化成功")
        except Exception as e:
            logger.error(f"TOS客户端初始化失败: {str(e)}")
            raise

    def upload_file(
        self,
        local_file_path: Union[str, Path],
        object_key: str,
        storage_class: str = "STANDARD",
        metadata: Optional[dict] = None,
    ) -> dict:
        """上传文件到TOS

        Args:
            local_file_path: 本地文件路径
            object_key: 对象存储中的文件路径
            storage_class: 存储类型，默认为标准存储
            metadata: 用户自定义元数据

        Returns:
            dict: 上传结果，包含状态码、请求ID等信息
        """
        try:
            local_file_path = Path(local_file_path)
            if not local_file_path.exists():
                raise FileNotFoundError(f"文件不存在: {local_file_path}")

            # 对于大文件使用分片上传
            file_size = local_file_path.stat().st_size
            if file_size > 100 * 1024 * 1024:  # 大于100MB使用分片上传
                return self._multipart_upload(
                    str(local_file_path), object_key, storage_class, metadata
                )

            # 小文件直接上传
            with open(local_file_path, "rb") as f:
                result = self.client.put_object(
                    self.bucket,
                    object_key,
                    content=f,
                    storage_class=getattr(
                        tos.StorageClassType, f"Storage_Class_{storage_class}"
                    ),
                    meta=metadata,
                )

                logger.info(f"文件上传成功: {object_key}")
                return {
                    "status_code": result.status_code,
                    "request_id": result.request_id,
                    "crc64": result.hash_crc64_ecma,
                    "object_key": object_key,
                }

        except tos.exceptions.TosClientError as e:
            logger.error(f"客户端错误: {e.message}, 原因: {e.cause}")
            raise
        except tos.exceptions.TosServerError as e:
            logger.error(
                f"服务端错误: 代码={e.code}, 请求ID={e.request_id}, "
                f"消息={e.message}, HTTP状态码={e.status_code}"
            )
            raise
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            raise

    def _multipart_upload(
        self,
        local_file_path: str,
        object_key: str,
        storage_class: str = "STANDARD",
        metadata: Optional[dict] = None,
    ) -> dict:
        """分片上传大文件

        Args:
            local_file_path: 本地文件路径
            object_key: 对象存储中的文件路径
            storage_class: 存储类型
            metadata: 用户自定义元数据

        Returns:
            dict: 上传结果
        """
        try:
            # 初始化分片上传
            init_result = self.client.init_multipart_upload(
                self.bucket,
                object_key,
                storage_class=getattr(
                    tos.StorageClassType, f"Storage_Class_{storage_class}"
                ),
                meta=metadata,
            )
            upload_id = init_result.upload_id

            # 计算分片大小和数量
            chunk_size = 20 * 1024 * 1024  # 20MB per chunk
            file_size = os.path.getsize(local_file_path)
            chunks_count = (file_size + chunk_size - 1) // chunk_size
            parts = []

            # 上传分片
            with open(local_file_path, "rb") as f:
                for i in range(chunks_count):
                    offset = chunk_size * i
                    f.seek(offset)
                    chunk = f.read(min(chunk_size, file_size - offset))

                    # 上传分片
                    part_result = self.client.upload_part(
                        self.bucket, object_key, upload_id, i + 1, content=chunk
                    )

                    parts.append({"PartNumber": i + 1, "ETag": part_result.etag})

                    logger.info(f"分片 {i+1}/{chunks_count} 上传完成")

            # 完成分片上传
            complete_result = self.client.complete_multipart_upload(
                self.bucket, object_key, upload_id, parts
            )

            logger.info(f"分片上传完成: {object_key}")
            return {
                "status_code": complete_result.status_code,
                "request_id": complete_result.request_id,
                "object_key": object_key,
            }

        except Exception as e:
            logger.error(f"分片上传失败: {str(e)}")
            # 清理未完成的分片上传
            try:
                self.client.abort_multipart_upload(self.bucket, object_key, upload_id)
            except Exception as abort_e:
                logger.error(f"清理未完成的分片上传失败: {str(abort_e)}")
            raise
