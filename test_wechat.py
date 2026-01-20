#!/usr/bin/env python3
"""测试企业微信Webhook是否正常工作"""

import os
import sys
import requests
import json

def test_wechat_webhook(webhook_url: str, test_content: str = None):
    """测试企业微信Webhook
    
    Args:
        webhook_url: 企业微信Webhook URL
        test_content: 测试内容，如果为None则使用默认测试内容
    """
    if not webhook_url:
        print("错误: 未提供Webhook URL")
        print("使用方法:")
        print("  python test_wechat.py <webhook_url>")
        print("  或设置环境变量: export WECHAT_WEBHOOK=<webhook_url>")
        sys.exit(1)
    
    # 默认测试内容
    if test_content is None:
        test_content = (
            "# 测试消息\n\n"
            "这是一条测试消息，用于验证企业微信Webhook是否正常工作。\n\n"
            "如果你看到这条消息，说明Webhook配置正确！\n\n"
            "测试时间: 2024年\n"
            "测试内容长度: 约100字符"
        )
    
    # 构建payload
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": test_content
        }
    }
    
    # 显示要发送的内容信息
    content_length = len(test_content)
    print(f"准备发送测试消息...")
    print(f"消息类型: Markdown")
    print(f"内容长度: {content_length} 字符")
    print(f"内容预览:\n{test_content[:200]}...\n")
    
    # 发送请求
    try:
        headers = {"Content-Type": "application/json"}
        print(f"正在发送到: {webhook_url[:50]}...")
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        
        print(f"HTTP状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("errcode") == 0:
                    print("\n✅ 测试成功！消息已发送到企业微信群。")
                    return True
                else:
                    print(f"\n❌ 测试失败！")
                    print(f"错误码: {result.get('errcode')}")
                    print(f"错误信息: {result.get('errmsg')}")
                    return False
            except ValueError:
                print(f"\n⚠️  响应不是JSON格式: {response.text}")
                return False
        else:
            print(f"\n❌ HTTP请求失败，状态码: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求异常: {e}")
        return False


def test_different_lengths(webhook_url: str):
    """测试不同长度的消息"""
    print("\n" + "="*60)
    print("测试不同长度的消息")
    print("="*60)
    
    test_cases = [
        ("短消息", "这是一条短消息测试。"),
        ("中等消息", "这是一条中等长度的消息。" * 50),
        ("长消息", "这是一条长消息测试。" * 200),
        ("超长消息", "这是一条超长消息测试。" * 500),
    ]
    
    for name, content in test_cases:
        print(f"\n测试: {name} (长度: {len(content)} 字符)")
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"# {name}\n\n{content}"
            }
        }
        
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"  ✅ 成功")
                else:
                    print(f"  ❌ 失败: {result.get('errmsg')}")
            else:
                print(f"  ❌ HTTP错误: {response.status_code}")
        except Exception as e:
            print(f"  ❌ 异常: {e}")


def test_exact_length(webhook_url: str):
    """测试精确长度限制"""
    print("\n" + "="*60)
    print("测试精确长度限制")
    print("="*60)
    
    # 测试不同长度
    test_lengths = [1000, 2000, 3000, 4000, 4096, 4100, 5000]
    
    for length in test_lengths:
        # 生成指定长度的内容
        content = "# 长度测试\n\n" + "测试内容。" * (length // 10)
        content = content[:length]
        
        actual_length = len(content)
        print(f"\n测试长度: {actual_length} 字符")
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"  ✅ 成功 (长度: {actual_length})")
                else:
                    print(f"  ❌ 失败: {result.get('errmsg')} (长度: {actual_length})")
                    if "4096" in result.get('errmsg', ''):
                        print(f"  💡 提示: 超过4096字符限制")
            else:
                print(f"  ❌ HTTP错误: {response.status_code}")
        except Exception as e:
            print(f"  ❌ 异常: {e}")


if __name__ == "__main__":
    # 从命令行参数或环境变量获取webhook URL
    if len(sys.argv) > 1:
        webhook_url = sys.argv[1]
    else:
        webhook_url = os.getenv("WECHAT_WEBHOOK") or os.getenv("WECHAT_WORK_WEBHOOK")
    
    if not webhook_url:
        print("错误: 未提供Webhook URL")
        print("\n使用方法:")
        print("  1. 命令行参数: python test_wechat.py <webhook_url>")
        print("  2. 环境变量: export WECHAT_WEBHOOK=<webhook_url>")
        print("  3. 环境变量: export WECHAT_WORK_WEBHOOK=<webhook_url>")
        sys.exit(1)
    
    print("="*60)
    print("企业微信Webhook测试工具")
    print("="*60)
    
    # 基础测试
    print("\n【基础测试】")
    success = test_wechat_webhook(webhook_url)
    
    if success:
        # 如果基础测试成功，进行更多测试
        print("\n是否进行更多测试？(y/n): ", end="")
        try:
            choice = input().strip().lower()
            if choice == 'y':
                test_different_lengths(webhook_url)
                test_exact_length(webhook_url)
        except KeyboardInterrupt:
            print("\n\n测试已取消。")
    else:
        print("\n基础测试失败，请检查Webhook URL是否正确。")
