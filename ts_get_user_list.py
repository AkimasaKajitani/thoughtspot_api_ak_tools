import requests
import pandas as pd
import json
from pathlib import Path
import time
import argparse
import sys
import re

# ===== 設定値 =====
# コマンドラインで指定がない場合ここの設定値が反映されます
# JSON setting -----#
JSON_FILE_PATH = "credential_format.json" # -jsonfile
ALL_ORG_PROCESSING = True          # -all
DIVIDE_FILES = True                # -divide
RECORD_SIZE = 50                   # -recordsize
# その他固定設定 ----------#
API_VERSION = '2.0'
SLEEP_TIME = 0.3
# ------------------------#

# ============= 本スクリプトの方針 ==============
# Pythonのモジュールは使用していません。
# APIの仕様変更があった際に、Pythonのモジュールを待つより直接APIを叩いた方が対応をまたなくて済むため
# ==========================================

# ============= コマンドラインサンプル ============= 
# python ts_get_user_list.py -j "credential_trial.json" -a -d -r 100
#    - credential_trial.json という設定ファイルを使用
#    - すべてのORGを処理します（設定ファイルがPrimaryOrgの場合）
#    - ファイルをORGごとに分割して生成します
#    - APIで一度に取得するレコード数を100にします# python ts_get_user_list.py -j "credential_trial.json"
# python ts_get_user_list.py -j "credential_trial.json"
#    - credential_trial.json という設定ファイルを使用
#    - 所属ORGのみ処理します
#    - ファイルはそれぞれひとかたまりで生成します
#    - APIで一度に取得するレコード数は50にします
# python ts_get_user_list.py
#    - 設定はすべてコードに書かれたデフォルト設定値で実行されます

# ============= 関数 =============================================
# [Internal Function] read_credential
# JSONファイルの読み込み
def read_credential(json_file):
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            my_thoughtspot_url = data['thoughtspot_url']
            data['base_url'] = f'{my_thoughtspot_url.rstrip('/')}/api/rest/{API_VERSION}/'
            stem = Path(json_file).stem
            settingname = stem.split("_")[-1]
            data['settingname'] = settingname

            # Error check
            if any(v is None or v == "" for v in data.values()):
                raise ValueError("未入力の項目があります。すべての設定値を埋めてください。")

            # log用
            print(f"thoughtspot_url: {data['thoughtspot_url']}")
            print(f"org_id(setting): {data['org_id']}")
            print(f"username: {data['username']}")

            return data
    except FileNotFoundError:
        print(f"{json_file}が見つかりません")
        return None
    except json.JSONDecodeError:
        print("JSONの読み込みに失敗しました")
        return None

# [Internal Function] write_credential
# JSONファイルへのSettingの書き込み
def write_credential(json_file, settings):
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        print(f"設定ファイル {json_file} を保存しました")
    except FileNotFoundError:
        print(f"{json_file}が見つかりません")
        return None
    except TypeError as e:
        print(f"エラー: JSONに変換できないデータが含まれています: {e}")
    except PermissionError:
        print(f"エラー: {json_file} への書き込み権限がありません")
    except OSError as e:
        print(f"OSエラーが発生しました (容量不足など): {e}")
    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}")
        exit(1)

# [Internal Function] apiaccess
# 戻り値がJSONの場合に使うAPI_ACCESS関数
def _apiaccess(base_url, session, endpoint, httpaction, header, postjson, privileges):
    endpointurl = base_url + endpoint
    try:
        print(f"Calling Endpoint {endpoint}...")

        # header update
        session.headers.update(header)

        # API Access(Actual)
        if httpaction == "post":
            resp = session.post(url=endpointurl, json=postjson)
        elif httpaction == "get":
            resp = session.get(url=endpointurl)
        else:
            pass

        # This method causes Python Exception to throw if status not 2XX
        resp.raise_for_status()

        # Retrieve the JSON body of response and convert into Dict
        # Some endpoints returns 204 not 200 for success, with no body, will error if you call .json() method
        resp_json = resp.json()

        return resp_json

    except requests.exceptions.HTTPError as e:
        # Catch HTTPError
        if resp.status_code == 403:
            print(f"{endpoint}でエラーが発生しました: 403 Forbidden - アクセスが拒否されました。")
            print(f"次の権限が必要です。 {privileges}")
            print(f"エラー詳細: {e}")
        else:
            print(f"その他のHTTPエラーが発生しました: {resp.status_code}")
            print(f"エラー詳細: {e}")
            print(e.response.content)

    except Exception as e:
        print("Something went wrong:"+endpointurl)
        print(e)
        print(e.request)
        print(e.request.url)
        print(e.request.headers)
        print(e.request.body)
        print(e.response.content)
        exit(1)

# [Internal Function] apiaccesses
def _apiaccesses(base_url, session, endpoint, httpaction, header, postjson, privileges, recordsize):
    # Initialize
    all_data = []
    page = 0

    #multiple api access
    while True: 
        postjson['record_offset'] = page
        # API access
        resp_json = _apiaccess(base_url, session, endpoint, httpaction, header, postjson, privileges)

        # 戻り値が空になるまで実行
        if not resp_json:
            break

        # 結果を追加
        all_data.extend(resp_json)

        # 何回APIを呼び出したか
        print(f"Endpoint {endpoint}: page {int(page/recordsize)}")

        page = (page + 1) * recordsize
        time.sleep(SLEEP_TIME) # Manner
    
    return all_data


# [TS API] Get Full Access Token
# 最初に使うフルアクセストークン取得用関数
# セッションはここで作成
def tsapi_get_full_access_token(settings):
    base_url = settings['base_url']
    if settings['org_id']!=-1:
        post_data = {
        "username": settings['username'],
        "password": settings['password'],
        "validity_time_in_sec": 300,
        "org_id" : settings['org_id'],
        "auto_create": False
        }
    else:
        post_data = {
        "username": settings['username'],
        "password": settings['password'],
        "validity_time_in_sec": 300,
        "auto_create": False
        }

    api_headers = {
    'X-Requested-By': 'ThoughtSpot',
    'Accept': 'application/json'
    }
    privileges = []
    endpoint = "auth/token/full"
 
    # Create a new Session object
    requests_session = requests.Session()

    # Access API Endpoint
    resp_json = _apiaccess(base_url, requests_session, endpoint, "post", api_headers, post_data, privileges)

    # Token
    token = resp_json["token"]
    print(f"Here's the token:{token[:10]}...")
    
    # Update api_headers from before with header for Bearer token
    api_headers['Authorization'] = 'Bearer {}'.format(token)
    requests_session.headers.update(api_headers)

    return requests_session

# [TS API] Get Current User Info
def tsapi_get_current_user_info(settings, session):
    base_url = settings['base_url']
    post_data = {}
    api_headers = {
    'X-Requested-By': 'ThoughtSpot',
    'Accept': 'application/json'
    }
    privileges = []
    endpoint = "auth/session/user"

    # Access API Endpoint
    resp_json = _apiaccess(base_url, session, endpoint, "get",  api_headers, post_data, privileges)
    
    return resp_json

# [TS API] Search Users
def tsapi_search_users(settings, session, orgs, recordsize):
    base_url = settings['base_url']
    post_data = {
    "record_offset": 0,
    "record_size": recordsize,
    "include_favorite_metadata": False,
    "org_identifiers": orgs
    }
    api_headers = {
    'X-Requested-By': 'ThoughtSpot',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
    }
    privileges = ["Can administer ThoughtSpot/Can manage users"]
    endpoint = "users/search"

    # Access API Endpoint(multiple access)
    resp_json = _apiaccesses(base_url, session, endpoint, "post", api_headers, post_data, privileges, recordsize)

    return resp_json

# [TS API] Search Orgs
def tsapi_search_orgs(settings, session):
    base_url = settings['base_url']
    post_data = {}
    api_headers = {
    'X-Requested-By': 'ThoughtSpot',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
    }
    privileges = ["Can administer Org/Can manage Orgs"]
    endpoint = "orgs/search"

    # Access API Endpoint
    resp_json = _apiaccess(base_url, session, endpoint, "post",  api_headers, post_data, privileges)
    
    return resp_json

# [TS API] Search User Groups
def tsapi_search_user_groups(settings, session, recordsize):
    base_url = settings['base_url']
    post_data = {
    "record_offset": 0,
    "record_size": recordsize,
    "include_users": False,
    "include_sub_groups": False
    }
    api_headers = {
    'X-Requested-By': 'ThoughtSpot',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
    }
    privileges = ["Can administer ThoughtSpot/Can manage groups"]
    endpoint = "groups/search"

    # Access API Endpoint
    resp_json = _apiaccesses(base_url, session, endpoint, "post", api_headers, post_data, privileges, recordsize)
    
    return resp_json

# [Support Function] extract_org_name
def _extract_org_name(orgs_str):
    # 欠損値（NaN）のチェック
    if pd.isna(orgs_str):
        return "No_Org"
    
    # 文字列に変換して正規表現で 'name': '...' の中身を抽出
    # シングルクォート、ダブルクォート両方に対応
    match = re.search(r"['\"]name['\"]:\s*['\"]([^'\"]+)['\"]", str(orgs_str))
    
    if match:
        return match.group(1)
    return "Unknown"

def cmdlineparser():
    # パーサーの作成
    parser = argparse.ArgumentParser(description="ThoughtSpotのユーザー一覧を取得する")

    # 引数の設定
    parser.add_argument("--jsonfile","-j", default=JSON_FILE_PATH, help="JSONファイルのパスを入力してください")
    parser.add_argument("--all","-a", action="store_true", help="すべてのORGを処理する")
    parser.add_argument("--divide","-d", action="store_true", help="ファイルをORGごとに分割して保存する")
    parser.add_argument("--recordsize","-r", type = int , default = RECORD_SIZE, help="APIで一度に取得するレコード数")

    # 引数の解析
    args = parser.parse_args()

    return args

# ============================= MAIN ==================================
def main(jsonfile, all_org_processing, divide_files, recordsize):
    try:
        # Load Cluster setting
        setting = read_credential(jsonfile)

        # Get Full Access Token(Session create)
        requests_session = tsapi_get_full_access_token(setting)

        # get_current_user_info
        current_org_info = tsapi_get_current_user_info(setting, requests_session)
        current_org_id = current_org_info['current_org']['id']
        current_org_name =  current_org_info['current_org']['name']
        print(f"org_id(actual): {current_org_id}({current_org_name})")

        if setting['org_id'] == -1:
            setting['org_id'] = current_org_id
            print(f"設定ファイルのorg_idをget_current_user_info APIで取得したorg_id {current_org_id} で更新しました。")
            # 設定ファイルに書き込み
            write_credential(jsonfile, setting)
        elif setting['org_id'] != current_org_id:
            print("設定ファイルのorg_idとget_current_user_info APIで取得したorg_idが不一致")
            print(f"設定ファイル org_id : {setting['org_id']}")
            print(f"get_current_user_info API の org_id : {current_org_id}")

        # ========= Get Org List ========= 
        if setting['org_id'] == 0:
            print("Processing org list...")
            orgs_json = tsapi_search_orgs(setting, requests_session)
            df_orgs = pd.json_normalize(orgs_json)
            print(df_orgs)
            ## CSV保存
            filename = f"ts_orglist_{setting['settingname']}.csv"
            df_orgs.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"Saved: {filename}")

        # ========= Get User Groups ========= 
        print("Processing User Groups list...")
        groups_json = tsapi_search_user_groups(setting, requests_session, recordsize)
        df_groups = pd.json_normalize(groups_json)

        # CSV保存
        if divide_files:
            # Org名を分解
            df_groups['org_name'] = df_groups['orgs'].apply(_extract_org_name)
            for org_name, group in df_groups.groupby('org_name'):
                filename = f"ts_usergrouplist_{setting['settingname']}_{org_name}.csv"
                
                group.drop(columns=['org_name']) # 保存用のorg_nameを削除
                group.to_csv(filename, index=False, encoding='utf-8-sig')
                print(f"Saved: {filename}")
        else:
            # Single File
            filename = f"ts_usergrouplist_{setting['settingname']}.csv"
            
            df_groups.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"Saved: {filename}")

        # ========= Get User List ========= 
        # org が 0 の時かつ ALL_ORG_PROCESSING = True の時はすべてのORGを取得する
        if setting['org_id']!=0:
            # Primary Orgではない
            orgs = [current_org_name]
        elif setting['org_id']==0 and not all_org_processing:
            # Primary OrgだがPrimary Orgのみ処理したい
            orgs = [current_org_name]
        else:
            # Primary Orgで全Orgを処理したい
            orgs = df_orgs['name'].tolist()

        if divide_files:
            for org in orgs:
                print(f"Processing...{org}")
                users_json = tsapi_search_users(setting, requests_session, org, recordsize)
                df_users = pd.json_normalize(users_json)
                ## CSV保存
                filename = f"ts_userlist_{setting['settingname']}_{org}.csv"
                df_users.to_csv(filename, index=False, encoding="utf-8-sig")
                print(f"Saved: {filename}")
        else:
            # Single File
            users_json = tsapi_search_users(setting, requests_session, orgs, recordsize)
            df_users = pd.json_normalize(users_json)
            ## CSV保存
            filename = f"ts_userlist_{setting['settingname']}.csv"
            df_users.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"Saved: {filename}")
    except ValueError as e:
        print(e)
    except Exception as e:
        print("何かしらエラーが発生しました。")
        print(e)

# ============================= MAIN(Only Commandline) ==================================
# プログラムを動かすとここが実行されます
if __name__ == "__main__":

    # ===== コマンドライン処理 ===== 
    # コマンドライン変数の取得
    args = cmdlineparser()
    print(f"Here is given command {sys.argv}")
    # コマンドライン指定がない場合は、Pythonコード内の定数を使う
    if len(sys.argv) == 1:
            args.jsonfile = JSON_FILE_PATH
            args.all = ALL_ORG_PROCESSING
            args.divide = DIVIDE_FILES
            args.recordsize = RECORD_SIZE

    print(f"Your command line option is {args}.")

    # ===== メイン処理 =====
    main(args.jsonfile, args.all, args.divide, args.recordsize)
