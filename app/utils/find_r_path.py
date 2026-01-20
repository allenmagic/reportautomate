import rpy2.situation
import os

print("--- rpy2 Diagnostics ---")
# 检查 rpy2 能否找到 R home
try:
    r_home = rpy2.situation.r_home()
    print(f"rpy2 detected R home: {r_home}")
    if r_home is None:
        print("rpy2 could not automatically detect R_HOME.")
        # 尝试从 PATH 查找
        import shutil
        r_executable = shutil.which("R")
        if r_executable:
            print(f"Found R executable via PATH: {r_executable}")
            # R_HOME is usually the parent directory of the directory containing the R executable
            potential_r_home = os.path.dirname(os.path.dirname(r_executable))
            print(f"Potential R_HOME based on PATH: {potential_r_home}")
            print(f"Consider setting R_HOME='{potential_r_home}' as an environment variable.")
        else:
            print("Could not find R executable in PATH.")

except Exception as e:
    print(f"Error getting R home from rpy2: {e}")

# 打印 R_HOME 环境变量 (如果设置了)
print(f"R_HOME environment variable: {os.environ.get('R_HOME')}")

# 打印更详细的信息
# print("\n--- Full rpy2 Situation Info ---")
# rpy2.situation.print_info()
print("------------------------")

# 尝试导入 r 核心对象
try:
    from rpy2.robjects import r
    print("Successfully imported rpy2.robjects.r")
    # 尝试执行一个简单的 R 命令
    r_version = r('R.version.string')
    print(f"Successfully executed R command. R version: {str(r_version[0])}")
except Exception as e:
    print(f"Error importing or using rpy2.robjects.r: {e}")