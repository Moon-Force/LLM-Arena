#!/bin/bash
# LLM Arena 启动脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== LLM Arena 启动脚本 ===${NC}"

function check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}错误: 未安装 $1${NC}"
        exit 1
    fi
}

function show_help() {
    echo "用法: ./start.sh [选项]"
    echo ""
    echo "选项:"
    echo "  frontend    仅启动前端开发服务器 (默认)"
    echo "  backend     仅启动后端 API 服务器"
    echo "  full        Docker 完整部署"
    echo "  dev         同时启动前后端（开发模式）"
    echo "  build       构建生产环境"
    echo "  stop        停止所有服务"
    echo "  logs        查看日志"
    echo "  help        显示帮助"
    echo ""
    echo "示例:"
    echo "  ./start.sh frontend    # 快速启动前端"
    echo "  ./start.sh full        # Docker 完整部署"
    echo "  ./start.sh dev         # 开发模式"
}

function start_frontend() {
    echo -e "${YELLOW}启动前端开发服务器...${NC}"
    check_command npm

    if [ ! -d "node_modules" ]; then
        echo -e "${BLUE}安装前端依赖...${NC}"
        npm install
    fi

    echo -e "${GREEN}前端运行在 http://localhost:5173${NC}"
    npm run dev
}

function start_backend() {
    echo -e "${YELLOW}启动后端 API 服务器...${NC}"
    check_command python

    if [ ! -d "venv" ]; then
        echo -e "${BLUE}创建虚拟环境...${NC}"
        python -m venv venv
    fi

    source venv/bin/activate

    if [ ! -f "venv/.installed" ]; then
        echo -e "${BLUE}安装 Python 依赖...${NC}"
        pip install -r requirements.txt
        touch venv/.installed
    fi

    echo -e "${GREEN}后端 API 运行在 http://localhost:8000${NC}"
    echo -e "${GREEN}API 文档 http://localhost:8000/docs${NC}"
    python -m opencode.api.server
}

function start_full() {
    echo -e "${YELLOW}Docker 完整部署...${NC}"
    check_command docker
    check_command docker-compose

    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}警告: 未找到 .env 文件，使用默认配置${NC}"
        echo -e "${YELLOW}请复制 .env.example 为 .env 并填入 API 密钥${NC}"
    fi

    docker-compose up -d --build

    echo -e "${GREEN}服务已启动！${NC}"
    echo -e "${GREEN}前端: http://localhost:5173${NC}"
    echo -e "${GREEN}后端 API: http://localhost:8000${NC}"
    echo -e "${GREEN}API 文档: http://localhost:8000/docs${NC}"
}

function start_dev() {
    echo -e "${YELLOW}开发模式启动...${NC}"
    start_backend &
    sleep 3
    start_frontend
}

function build_prod() {
    echo -e "${YELLOW}构建生产环境...${NC}"
    npm install
    npm run build
    docker-compose build
    echo -e "${GREEN}构建完成！${NC}"
}

function stop_all() {
    echo -e "${YELLOW}停止所有服务...${NC}"
    docker-compose down 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    pkill -f "opencode.api.server" 2>/dev/null || true
    echo -e "${GREEN}所有服务已停止${NC}"
}

case "${1:-frontend}" in
    frontend)
        start_frontend
        ;;
    backend)
        start_backend
        ;;
    full)
        start_full
        ;;
    dev)
        start_dev
        ;;
    build)
        build_prod
        ;;
    stop)
        stop_all
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}未知选项: $1${NC}"
        show_help
        exit 1
        ;;
esac
