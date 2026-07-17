@echo off
REM LLM Arena Windows 启动脚本

setlocal EnableDelayedExpansion

:: 颜色设置
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "BLUE=[94m"
set "NC=[0m"

echo %BLUE%=== LLM Arena 启动脚本 ===%NC%

:: 显示帮助
if "%~1"=="help" goto :show_help
if "%~1"=="--help" goto :show_help
if "%~1"=="-h" goto :show_help

:: 默认启动前端
if "%~1"=="" set "arg=frontend" else set "arg=%~1"

:: 检查 Node.js
if "%~1"=="frontend" goto :check_node
if "%~1"=="dev" goto :check_node
if "%~1"=="build" goto :check_node

:: 检查 Python
if "%~1"=="backend" goto :check_python
if "%~1"=="dev" goto :check_python

:: 检查 Docker
if "%~1"=="full" goto :check_docker
if "%~1"=="stop" goto :check_docker
if "%~1"=="logs" goto :check_docker

:: 启动前端
goto :start_frontend

:check_node
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%错误: 未安装 Node.js%NC%
    echo 请从 https://nodejs.org/ 下载安装
    exit /b 1
)
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%错误: 未安装 npm%NC%
    exit /b 1
)
goto :eof

:check_python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%错误: 未安装 Python%NC%
    echo 请从 https://python.org/ 下载安装
    exit /b 1
)
goto :eof

:check_docker
where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%错误: 未安装 Docker%NC%
    echo 请从 https://docs.docker.com/get-docker/ 下载安装
    exit /b 1
)
where docker-compose >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %RED%错误: 未安装 Docker Compose%NC%
    exit /b 1
)
goto :eof

:start_frontend
echo %YELLOW%启动前端开发服务器...%NC%

if not exist "node_modules" (
    echo %BLUE%安装前端依赖...%NC%
    call npm install
)

echo %GREEN%前端运行在 http://localhost:5173%NC%
call npm run dev
goto :eof

:start_backend
echo %YELLOW%启动后端 API 服务器...%NC%

:: 检查虚拟环境
if not exist "venv" (
    echo %BLUE%创建虚拟环境...%NC%
    python -m venv venv
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 安装依赖
if not exist "venv\.installed" (
    echo %BLUE%安装 Python 依赖...%NC%
    pip install -r requirements.txt
    type nul > venv\.installed
)

echo %GREEN%后端 API 运行在 http://localhost:8000%NC%
echo %GREEN%API 文档 http://localhost:8000/docs%NC%
python -m opencode.api.server
goto :eof

:start_full
echo %YELLOW%Docker 完整部署...%NC%

:: 检查 .env 文件
if not exist ".env" (
    echo %YELLOW%警告: 未找到 .env 文件，使用默认配置%NC%
    echo %YELLOW%请复制 .env.example 为 .env 并填入 API 密钥%NC%
)

:: 构建并启动
docker-compose up -d --build

echo %GREEN%服务已启动！%NC%
echo %GREEN%前端: http://localhost:5173%NC%
echo %GREEN%后端 API: http://localhost:8000%NC%
echo %GREEN%API 文档: http://localhost:8000/docs%NC%
echo.
echo %BLUE%查看日志: docker-compose logs -f%NC%
echo %BLUE%停止服务: docker-compose down%NC%
goto :eof

:build_prod
echo %YELLOW%构建生产环境...%NC%

:: 构建前端
echo %BLUE%构建前端...%NC%
call npm install
call npm run build

:: 构建 Docker 镜像
echo %BLUE%构建 Docker 镜像...%NC%
docker-compose build

echo %GREEN%构建完成！%NC%
goto :eof

:stop_all
echo %YELLOW%停止所有服务...%NC%

:: 停止 Docker 服务
docker-compose down 2>nul

:: 停止前端进程
taskkill /F /IM node.exe 2>nul

echo %GREEN%所有服务已停止%NC%
goto :eof

:show_logs
docker-compose logs -f
goto :eof

:show_help
echo 用法: start.bat [选项]
echo.
echo 选项:
echo   frontend    仅启动前端开发服务器
echo   backend     仅启动后端 API 服务器
echo   full        启动完整 Docker 环境
echo   dev         同时启动前后端（开发模式）
echo   build       构建生产环境
echo   stop        停止所有服务
echo   logs        查看日志
echo   help        显示帮助
echo.
echo 示例:
echo   start.bat frontend    快速启动前端
echo   start.bat full        Docker 完整部署
echo   start.bat dev         开发模式
goto :eof

:: 主逻辑
if "%arg%"=="frontend" goto :start_frontend
if "%arg%"=="backend" goto :start_backend
if "%arg%"=="full" goto :start_full
if "%arg%"=="dev" goto :start_dev
if "%arg%"=="build" goto :build_prod
if "%arg%"=="stop" goto :stop_all
if "%arg%"=="logs" goto :show_logs

echo %RED%未知选项: %arg%%NC%
goto :show_help
