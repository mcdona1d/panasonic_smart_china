import requests
import json
import hashlib
import urllib.parse

# ================= 配置区域 =================
USERNAME = "你的手机号"
PASSWORD = "你的密码"
# ===========================================

# API 地址常量
URL_GET_TOKEN = "https://app.psmartcloud.com/App/UsrGetToken"
URL_LOGIN = "https://app.psmartcloud.com/App/UsrLogin"
URL_GET_DEV = "https://app.psmartcloud.com/App/UsrGetBindDevInfo"

def get_headers(ssid=None):
    headers = {
        'User-Agent': 'SmartApp',
        'Content-Type': 'application/json',
    }
    if ssid:
        headers['Cookie'] = f"SSID={ssid}"
    return headers

def login_and_get_devices():
    session = requests.Session()
    
    print(f"1. 正在获取 Token (用户: {USERNAME})...")
    # 1. GetToken
    try:
        resp = session.post(URL_GET_TOKEN, json={
            "id": 1, "uiVersion": 4.0, "params": {"usrId": USERNAME}
        }, headers=get_headers(), verify=False)
        
        data = resp.json()
        if 'results' not in data:
            print("获取 Token 失败:", data)
            return None, None, None
        token_start = data['results']['token']
        
        print("2. 正在计算加密哈希并登录...")
        # 2. 计算密码哈希
        pwd_md5 = hashlib.md5(PASSWORD.encode()).hexdigest().upper()
        inter_md5 = hashlib.md5((pwd_md5 + USERNAME).encode()).hexdigest().upper()
        final_token = hashlib.md5((inter_md5 + token_start).encode()).hexdigest().upper()
        
        # 3. Login
        resp = session.post(URL_LOGIN, json={
            "id": 2, "uiVersion": 4.0, 
            "params": {"telId": "00:00:00:00:00:00", "checkFailCount": 0, "usrId": USERNAME, "pwd": final_token}
        }, headers=get_headers(), verify=False)
        
        login_res = resp.json()
        if "results" not in login_res:
            print("登录失败:", login_res)
            return None, None, None
            
        res = login_res['results']
        real_usr_id = res['usrId']
        ssid = res['ssId']
        family_id = res['familyId']
        real_family_id = res['realFamilyId']
        
        print(f"   登录成功! SSID: {ssid[:10]}... UsrId: {real_usr_id}")
        
        print("3. 正在获取设备列表...")
        # 4. Get Devices
        resp = session.post(URL_GET_DEV, json={
            "id": 3, "uiVersion": 4.0,
            "params": {"realFamilyId": real_family_id, "familyId": family_id, "usrId": real_usr_id}
        }, headers=get_headers(ssid), verify=False)
        
        dev_res = resp.json()
        if 'results' not in dev_res:
            print("获取设备列表失败")
            return None, None, None
            
        return real_usr_id, ssid, dev_res['results']['devList']
    except Exception as e:
        print(f"发生错误: {e}")
        return None, None, None

def generate_html_link(usr_id, ssid, device):
    """
    根据设备信息生成控制页面 URL
    """
    params = device['params']
    device_id = device['deviceId']
    device_name = params.get('deviceName', 'Unknown Device')
    
    # 获取设备子类型 (AirconET, VentET 等)
    sub_type = params.get('devSubTypeId', 'AirconET')
    
    # URL 编码中文名称
    device_name_encoded = urllib.parse.quote(device_name)
    
    # === 修改点：动态解析 category_id ===
    # deviceId 格式通常为: MAC_CATEGORY_SUFFIX (例如: 4024B2610ECF_0900_6838)
    parts = device_id.split('_')
    if len(parts) >= 3:
        # 取中间的部分作为 category_id
        category_id = parts[1]
    else:
        # 如果格式不标准，使用默认值 0900
        category_id = "0900"
    
    # 构建基础 URL
    base_url = f"https://app.psmartcloud.com/ca/cn/{category_id}/{sub_type}/index.html"
    
    # 拼接参数
    query_params = (
        f"?deviceId={device_id}"
        f"&devType=" 
        f"&usrId={usr_id}"
        f"&SSID={ssid}"
        f"&deviceName={device_name_encoded}"
    )
    
    full_url = base_url + query_params + "#topPage"
    return device_name, sub_type, category_id, full_url

if __name__ == "__main__":
    # 忽略 SSL 警告
    requests.packages.urllib3.disable_warnings()
    
    usr_id, ssid, dev_list = login_and_get_devices()
    
    if dev_list:
        print("\n" + "="*80)
        print(f"发现 {len(dev_list)} 个设备，生成的调试链接如下：")
        print("="*80 + "\n")
        
        for dev in dev_list:
            name, sub_type, cat_id, url = generate_html_link(usr_id, ssid, dev)
            print(f"设备名称: {name}")
            print(f"设备类型: {sub_type} (Category: {cat_id})")
            print(f"DeviceID: {dev['deviceId']}")
            print(f"控制链接: \n{url}")
            print("-" * 80)
            
        print("\n提示：请在浏览器(推荐手机模式)打开上述链接，打开开发者工具(F12) -> Network，进行操作抓包。")
    else:
        print("未找到设备或登录失败。")