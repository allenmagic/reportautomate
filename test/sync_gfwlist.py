import urllib.request
import base64
import re
import os

# --- 配置区 ---
GFWLIST_URL = "https://raw.githubusercontent.com/gfwlist/gfwlist/master/gfwlist.txt"
# 选一个可靠的远程 DNS 供 Dnsmasq 解析黑名单域名
REMOTE_DNS = "8.8.8.8"
# 对应之前 nftables 脚本中定义的集合名称
NFTSET_NAME = "4#inet#fw4#proxy_set"
# 输出文件名
OUTPUT_FILE = "gfw_list.conf"


def fetch_gfwlist():
    print("正在下载 GFWList...")
    try:
        content = urllib.request.urlopen(GFWLIST_URL, timeout=15).read()
        return base64.b64decode(content).decode('utf-8')
    except Exception as e:
        print(f"下载失败: {e}")
        return None


def parse_gfwlist(content):
    domains = set()
    # 匹配规则：排除注释、IP地址、正则符号
    for line in content.splitlines():
        if not line or line.startswith('!') or line.startswith('['):
            continue

        # 简化提取逻辑
        domain = line.replace('||', '').replace('http://', '').replace('https://', '')
        domain = domain.split('/')[0].split(':')[0]

        # 仅保留有效的域名格式 (简单正则)
        if re.match(r'^[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', domain):
            domains.add(domain)

    return sorted(list(domains))


def generate_conf(domains):
    print(f"解析完成，共计 {len(domains)} 个有效域名。")
    with open(OUTPUT_FILE, 'w') as f:
        f.write(f"# GFWList Auto Generated\n")
        for domain in domains:
            # 写入 DNS 规则
            f.write(f"server=/{domain}/{REMOTE_DNS}\n")
            # 写入 nftset 规则
            f.write(f"nftset=/{domain}/{NFTSET_NAME}\n")
    print(f"配置文件已保存至: {OUTPUT_FILE}")


if __name__ == "__main__":
    raw_content = fetch_gfwlist()
    if raw_content:
        domain_list = parse_gfwlist(raw_content)
        generate_conf(domain_list)

        print("\n--- 后续操作建议 ---")
        print(f"1. 将 {OUTPUT_FILE} 上传至 OpenWrt 的 /etc/dnsmasq.d/")
        print("2. 执行: /etc/init.d/dnsmasq restart")