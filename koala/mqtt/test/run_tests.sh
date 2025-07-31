#!/bin/bash

# MQTT + Celery 測試套件執行腳本
# 用於快速運行IoT架構測試

set -e  # 遇到錯誤時退出

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函數：打印帶顏色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 函數：檢查Docker服務狀態
check_services() {
    print_info "檢查Docker服務狀態..."

    # 檢查必要的服務是否運行
    services=("koala-koala-1" "koala-koala-iot-default-worker-1" "koala-koala-mqtt-client-1" "koala-koala-rabbitmq-1" "koala-koala-redis-1")

    for service in "${services[@]}"; do
        if docker ps --format "table {{.Names}}" | grep -q "$service"; then
            print_success "服務 $service 正在運行"
        else
            print_error "服務 $service 未運行"
            return 1
        fi
    done

    print_success "所有必要服務都在運行"
    return 0
}

# 函數：啟動服務
start_services() {
    print_info "啟動Docker服務..."

    if docker-compose -f backend-local.yml up -d; then
        print_success "服務啟動成功"

        # 等待服務完全啟動
        print_info "等待服務完全啟動..."
        sleep 10

        # 檢查服務狀態
        if check_services; then
            print_success "所有服務已準備就緒"
        else
            print_error "部分服務啟動失敗"
            exit 1
        fi
    else
        print_error "服務啟動失敗"
        exit 1
    fi
}

# 函數：運行測試
run_tests() {
    local include_iot_simulator=$1

    print_info "開始運行測試套件..."

    if [ "$include_iot_simulator" = "true" ]; then
        print_info "包含IoT設備模擬器測試"
        docker-compose -f backend-local.yml exec koala-iot-default-worker python koala/mqtt/test/run_all_tests.py --include-iot-simulator
    else
        print_info "僅運行基本架構測試"
        docker-compose -f backend-local.yml exec koala-iot-default-worker python koala/mqtt/test/run_all_tests.py
    fi
}

# 函數：顯示幫助信息
show_help() {
    echo "MQTT + Celery 測試套件執行腳本"
    echo ""
    echo "用法: $0 [選項]"
    echo ""
    echo "選項:"
    echo "  -h, --help              顯示此幫助信息"
    echo "  -s, --start             啟動Docker服務"
    echo "  -c, --check             檢查服務狀態"
    echo "  -t, --test              運行基本測試 (不包含IoT模擬器)"
    echo "  -f, --full              運行完整測試 (包含IoT模擬器)"
    echo "  -r, --restart           重啟服務並運行完整測試"
    echo "  -l, --logs              顯示服務日誌"
    echo ""
    echo "示例:"
    echo "  $0 --start              # 啟動服務"
    echo "  $0 --test               # 運行基本測試"
    echo "  $0 --full               # 運行完整測試"
    echo "  $0 --restart            # 重啟服務並運行完整測試"
    echo ""
}

# 函數：顯示日誌
show_logs() {
    print_info "顯示服務日誌..."
    echo ""
    echo "=== MQTT客戶端日誌 ==="
    docker-compose -f backend-local.yml logs koala-mqtt-client --tail=20
    echo ""
    echo "=== Celery Worker日誌 ==="
    docker-compose -f backend-local.yml logs koala-iot-default-worker --tail=20
    echo ""
    echo "=== RabbitMQ日誌 ==="
    docker-compose -f backend-local.yml logs koala-rabbitmq --tail=10
}

# 主函數
main() {
    # 檢查是否有參數
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi

    # 解析參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -s|--start)
                start_services
                exit 0
                ;;
            -c|--check)
                check_services
                exit $?
                ;;
            -t|--test)
                if check_services; then
                    run_tests false
                else
                    print_error "服務未運行，請先使用 --start 啟動服務"
                    exit 1
                fi
                exit 0
                ;;
            -f|--full)
                if check_services; then
                    run_tests true
                else
                    print_error "服務未運行，請先使用 --start 啟動服務"
                    exit 1
                fi
                exit 0
                ;;
            -r|--restart)
                print_info "重啟服務..."
                docker-compose -f backend-local.yml down
                start_services
                run_tests true
                exit 0
                ;;
            -l|--logs)
                show_logs
                exit 0
                ;;
            *)
                print_error "未知選項: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 執行主函數
main "$@"
