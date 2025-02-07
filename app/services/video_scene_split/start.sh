#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的信息
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否安装了必要的工具
check_requirements() {
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    if ! command -v docker compose &> /dev/null; then
        error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
}

# 创建系统用户
create_system_user() {
    info "创建 transnet 系统用户..."
     if ! id -u transnet &>/dev/null; then
        sudo useradd -r -u 1000 -g 1000 -s /sbin/nologin transnet
        info "已创建 transnet 用户（UID=1000, GID=1000）"
    else
        # 检查现有用户的 UID 和 GID
        current_uid=$(id -u transnet)
        current_gid=$(id -g transnet)
        if [ "$current_uid" != "1000" ] || [ "$current_gid" != "1000" ]; then
            warn "transnet 用户存在但 UID/GID 不匹配，正在修改..."
            sudo usermod -u 1000 transnet
            sudo groupmod -g 1000 transnet
            info "已更新 transnet 用户 UID/GID 为 1000"
        else
            warn "transnet 用户已存在且 UID/GID 正确"
        fi
    fi
}

# 创建必要的目录结构
create_directories() {
    info "创建目录结构..."
    mkdir -p server/input server/output
    
    # 设置目录所有者为 transnet 用户并设置权限
    sudo chown -R transnet:transnet .
    sudo find . -type d -exec chmod 755 {} \;
    sudo find . -type f -exec chmod 644 {} \;
    
    # 特别设置 server/input 和 server/output 目录的权限
    sudo chown -R transnet:transnet server/input server/output
    sudo chmod -R 770 server/input server/output
    
    # 设置 server/input 和 server/output 目录的默认 ACL
    sudo setfacl -R -d -m u:transnet:rwx server/input server/output
    sudo setfacl -R -d -m g:transnet:rwx server/input server/output
    sudo setfacl -R -m u:transnet:rwx server/input server/output
    sudo setfacl -R -m g:transnet:rwx server/input server/output
    
    info "已设置目录权限和默认 ACL"
}

# 启动服务
start_services() {
    info "启动 TransNetV2 服务..."
    docker compose up -d

    if [ $? -eq 0 ]; then
        info "服务启动成功！"
        echo -e "\n${GREEN}=== 服务管理命令 ===${NC}"
        echo -e "启动服务：${YELLOW}docker compose up -d${NC}"
        echo -e "停止服务：${YELLOW}docker compose down${NC}"
        echo -e "查看日志：${YELLOW}docker compose logs -f${NC}"
        echo -e "\n${GREEN}=== API 接口信息 ===${NC}"
        echo -e "服务地址：${YELLOW}http://localhost:5000${NC}"
        echo -e "场景检测：${YELLOW}POST http://localhost:5000/detect_scenes${NC}"
    else
        error "服务启动失败，请检查错误信息"
        exit 1
    fi
}

# 主函数
main() {
    info "开始配置 TransNetV2 环境..."
    
    # 检查依赖
    check_requirements
    
    # 创建系统用户
    create_system_user
    
    # 创建目录
    create_directories
    
    # 启动服务
    start_services
}

# 执行主函数
main