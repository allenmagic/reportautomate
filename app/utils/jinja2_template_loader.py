# jinja2_template_loader.py
# -*- coding: utf-8 -*-

import os
import re
from jinja2 import Environment, FileSystemLoader,StrictUndefined
from app.utils.logger import logger


# 转义函数
def elatex(text):
    """
    对数据中的原文内容的特殊字符进行转义处理。

    参数:
    text (str): 需要转义的文本

    返回:
    str: 转义后的文本
    """
    special_chars = {
        u'$': u'\\$',
        u'%': u'\\%',
        u'&': u'\\&',
        u'#': u'\\#',
        u'_': u'\\_',
        u'{': u'\\{',
        u'}': u'\\}',
        u'[': u'{[}',
        u']': u'{]}',
        u'"': u"{''}",
        # u'\\': u'\\textbackslash{}',
        u'~': u'\\textasciitilde{}',
        u'<': u'\\textless{}',
        u'>': u'\\textgreater{}',
        u'^': u'\\textasciicircum{}',
        u'`': u'{}`',  # avoid ?` and !`
    }

    # 使用正则表达式来替换字符，以防止反复转义问题
    pattern = re.compile(r'([{}])'.format(''.join(re.escape(char) for char in special_chars.keys())))
    escaped_text = pattern.sub(lambda m: special_chars[m.group()], text).replace('\n\n', '\n\par\n')

    return escaped_text


def load_template(template_folder:str, template_name:str):
    """
    加载Jinja2模板文件

    Parameters:
    template_folder (str): 模板文件夹路径
    template_name (str): 模板文件名称

    Returns:
    Template: 渲染后的Jinja2模板对象
    """

    # 检查模板文件目录是否存在
    if not os.path.isdir(template_folder):
        raise FileNotFoundError(f"Template folder not found: {template_folder}")
    print("Template folder exists:", True)

    # 设置Jinja2环境
    env = Environment(
        loader=FileSystemLoader(template_folder),
        block_start_string='(%',
        block_end_string='%)',
        variable_start_string='((',
        variable_end_string='))',
        comment_start_string='(#',
        comment_end_string='#)',
        undefined=StrictUndefined
    )

    # 构建完整的模板文件路径
    template_path = os.path.join(template_folder, template_name)

    # 检查模板文件是否存在
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"模板路径有误，请检查: {template_path}")
    print("Template file exists:", True)

    # 将转义函数注册为Jinja2过滤器
    env.filters['elatex'] = elatex

    # 加载模板
    return env.get_template(template_name)