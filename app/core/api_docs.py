"""API文档配置"""

API_HELP_CONTENT = {
    "api_version": "1.0.1",
    "authentication": {
        "type": "Header Authentication",
        "headers": {
            "X-App-ID": "Your application ID",
            "X-App-Secret": "Your application secret"
        },
        "note": "所有 /api 路径下的接口都需要认证"
    },
    "endpoints": [
        # 文件解压相关
        {
            "path": "/api/unzip",
            "method": "POST",
            "description": "下载并解压ZIP文件",
            "body": {
                "task_id": "任务ID",
                "attachment_id": "附件ID",
                "download_url": "ZIP文件下载URL",
                "unzip_passwd": "ZIP文件密码(可选)"
            },
            "response": {
                "task_id": "任务ID",
                "attachment_id": "附件ID",
                "success": "处理是否成功",
                "message": "处理结果信息",
                "files": "解压后的文件列表"
            }
        },
        {
            "path": "/api/unzip/form",
            "method": "POST",
            "description": "使用表单提交下载并解压ZIP文件",
            "form_fields": [
                "task_id - 任务ID",
                "attachment_id - 附件ID",
                "download_url - ZIP文件下载URL",
                "unzip_passwd - ZIP文件密码(可选)"
            ]
        },
        {
            "path": "/api/download/{task_id}/{file_path}",
            "method": "GET",
            "description": "下载解压后的文件内容",
            "parameters": {
                "task_id": "任务ID",
                "file_path": "文件路径"
            }
        },
        {
            "path": "/api/files/{task_id}",
            "method": "GET",
            "description": "获取任务的文件列表",
            "parameters": {
                "task_id": "任务ID"
            }
        },
        {
            "path": "/api/cleanup/{task_id}",
            "method": "DELETE",
            "description": "清理任务的临时文件",
            "parameters": {
                "task_id": "任务ID"
            }
        },

        # PDF密码移除相关
        {
            "path": "/api/pdf/remove_passwd",
            "method": "POST",
            "description": "移除PDF文件密码保护",
            "body": {
                "task_id": "任务ID，用于标识本次处理",
                "attachment_id": "附件ID，用于标识文件",
                "download_url": "PDF文件的下载链接",
                "passwd": "可能的密码列表，将逐一尝试"
            },
            "response": {
                "task_id": "任务ID",
                "attachment_id": "附件ID",
                "success": "处理是否成功",
                "message": "处理结果信息",
                "error": "错误信息，当success为false时提供",
                "download_url": "解密后的PDF文件下载链接"
            }
        },
        {
            "path": "/api/pdf/remove_passwd/form",
            "method": "POST",
            "description": "通过表单提交移除PDF密码保护的请求",
            "form_fields": [
                "task_id - 任务ID",
                "attachment_id - 附件ID",
                "download_url - PDF文件下载URL",
                "passwd - 可能的密码列表，以逗号分隔"
            ]
        },
        {
            "path": "/api/pdf/download/{task_id}/{attachment_id}",
            "method": "GET",
            "description": "下载已解密的PDF文件",
            "parameters": {
                "task_id": "任务ID",
                "attachment_id": "附件ID"
            },
            "response": "二进制PDF文件流"
        },
        {
            "path": "/api/pdf/cleanup/{task_id}",
            "method": "DELETE",
            "description": "清理PDF任务相关的临时文件",
            "parameters": {
                "task_id": "任务ID"
            }
        },

        # SharePoint文件上传
        {
            "path": "/api/sharepoint/upload",
            "method": "POST",
            "description": "上传文件到SharePoint",
            "body": {
                "task_id": "任务ID",
                "file_path": "文件路径",
                "target_folder": "目标文件夹"
            }
        },

        # 附件处理
        {
            "path": "/api/process_attachment",
            "method": "POST",
            "description": "处理邮件附件",
            "form_fields": [
                "task_id - 任务ID",
                "attachment_data - 附件数据"
            ]
        },

        # 银行数据处理
        {
            "path": "/api/process_hsbc_daily_cash",
            "method": "POST",
            "description": "处理HSBC每日现金数据",
            "form_fields": [
                "email_id - 邮件ID",
                "file_path - HSBC现金日报文件路径"
            ],
            "response": {
                "success": "处理是否成功",
                "data": "提取的现金数据",
                "message": "处理结果信息"
            }
        },
        {
            "path": "/api/process_citi_monthly_statement",
            "method": "POST",
            "description": "处理花旗银行月度交易记录",
            "form_fields": [
                "email_id - 邮件ID",
                "file_path - 月度账单文件路径"
            ],
            "response": {
                "success": "处理是否成功",
                "transactions": "交易记录列表",
                "message": "处理结果信息"
            }
        },
        {
            "path": "/api/process_hsbc_monthly_statement",
            "method": "POST",
            "description": "处理HSBC月度交易记录",
            "form_fields": [
                "email_id - 邮件ID",
                "file_path - 月度账单文件路径"
            ],
            "response": {
                "success": "处理是否成功",
                "transactions": "交易记录列表",
                "message": "处理结果信息"
            }
        },
        {
            "path": "/api/process_citi_daily_balance",
            "method": "POST",
            "description": "处理花旗银行日活期余额报告",
            "form_fields": [
                "file_path - 本地文件路径或者URL地址"
            ],
            "response": {
                "success": "处理是否成功",
                "balance_data": "余额数据",
                "message": "处理结果信息"
            }
        },

        # PDF文档渲染
        {
            "path": "/api/render_pdf_doc",
            "method": "POST",
            "description": "使用LaTeX + Jinja2模板渲染生成PDF文件",
            "body": {
                "task_id": "任务ID",
                "file_name": "生成的文件名(可选)",
                "record_id": "记录ID(可选)",
                "template_name": "模板名称",
                "data": "渲染数据(JSON对象)"
            },
            "response": {
                "task_id": "任务ID",
                "record_id": "记录ID",
                "pdf": "Base64编码的PDF内容",
                "render_engine": "渲染引擎(latex)"
            }
        },
        {
            "path": "/api/render_typst_pdf",
            "method": "POST",
            "description": "使用Typst模板渲染生成PDF文件",
            "body": {
                "task_id": "任务ID",
                "file_name": "生成的文件名(可选)",
                "record_id": "记录ID(可选)",
                "template_name": "模板名称",
                "data": "渲染数据(JSON对象)"
            },
            "response": {
                "task_id": "任务ID",
                "record_id": "记录ID",
                "pdf": "Base64编码的PDF内容",
                "render_engine": "渲染引擎(typst)"
            },
            "note": "Typst是一个现代化的排版系统，相比LaTeX更快速简洁"
        },

        # GIIN搜索
        {
            "path": "/api/giin_search",
            "method": "POST",
            "description": "根据主体名称搜索GIIN(全球中介机构识别号)",
            "form_fields": [
                "record_id - 记录ID",
                "data - 搜索数据(JSON格式)"
            ],
            "response": {
                "success": "搜索是否成功",
                "giin": "GIIN号码",
                "entity_info": "主体信息",
                "message": "处理结果信息"
            }
        },

        # PDF转Markdown
        {
            "path": "/api/pdf_to_markdown",
            "method": "POST",
            "description": "将PDF文件转换为Markdown文本",
            "form_fields": [
                "file_path - PDF文件路径"
            ],
            "response": {
                "success": "转换是否成功",
                "markdown": "转换后的Markdown文本",
                "message": "处理结果信息"
            }
        }
    ],

    "common_responses": {
        "success_response": {
            "success": True,
            "message": "操作成功",
            "data": "具体数据"
        },
        "error_response": {
            "success": False,
            "error": "错误信息",
            "message": "详细错误描述"
        },
        "authentication_error": {
            "detail": "Invalid authentication credentials",
            "status_code": 401
        }
    },

    "notes": [
        "所有时间戳均为UTC时间",
        "文件路径支持本地路径和HTTP(S) URL",
        "大文件上传建议使用分片上传",
        "临时文件会在24小时后自动清理",
        "PDF渲染支持LaTeX和Typst两种引擎"
    ]
}
