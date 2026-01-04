# ts_get_user_list.py

## 概要
ThoughtSpotのユーザー一覧を取得します。
ユーザー一覧の取得の際、Orgの一覧とUserGroupの一覧も取得します。

- 設定は専用のJSONファイルで行います
- ユーザーリストの取得を行います
- グループリストの取得を行います
- 設定ファイルがPrimaryOrg（0）の場合、以下のことが実行可能です
    - ORGリストの取得
    - すべてのORGに対してユーザーリストを取得
    - すべてのORG内のグループリストを取得
- コマンドラインもしくはVS Codeなどの直接Pythonのコードを実行する環境でも実行可能です
- 以下のパッケージが追加で必要です（pipインストールしてください）
    - pandas
    - requests

## 追加パッケージのインストール方法

以下のコマンドをコマンドラインで実行してください。

    pip install requests pandas

## 設定ファイル書式
設定ファイルは以下のJSON形式としています。設定ファイルをわかりやすくするため、ファイルの頭は「credential」としています。その後ろのアンダーバー以下は設定ファイルを区別するための名称です。この名称は各リストに付与されます。

例：credential_yourcompanyname.json

上の例の場合、各出力ファイルに「yourcompanyname」が付与されます。

### 設定ファイルの内容

本スクリプトでは、credential_XXX.json という設定ファイルを使いします。このJSONファイルに、ThoughtSpotのURL、アカウント情報、シークレットトークンなどを記載するようにしています。ファイルベースにしているのは、複数環境を簡単に切り替えられるためです。

    {
        "thoughtspot_url": "https://YOUR_CLUSTER_NAME.thoughtspot.cloud",
        "org_id": -1,
        "username": "",
        "password": "",
        "secret_key": ""
    }

#### org_id
PrimaryOrgの場合は「Org_id」は0です。それ以外の場合は、Playground 2.0のGet Current User InfoにてOrg_idを確認できます。Get Current User Infoを実行したとき「current_org」という項目のidが該当のorg_idです。
Enterprise以外（トライアルも含む）ではこの情報が必要になりますが、アクセストークンでどのOrgなのか自動的に判断されるため、間違っていてもおそらく問題ないと思われます。

-1で設定ファイルを設定しておけば、自動的にGet Current User Infoを実行してorg_idを更新するようにしています。

#### username, password

アクセストークン（secret_key）を取得したユーザーのusernameとpasswordを記載します。一部のAPIは、実行するための権限（主に管理者系の権限）が必要になるのでご注意ください。

#### secret_key

ナビゲーションの「開発」タブの「セキュリティ設定」にある「信頼できる認証」を有効化することでトークンが取得できます。このトークンを貼り付けてください。くれぐれもトークンの取り扱いにはご注意ください。



## コマンドライン引数説明

コマンドライン引数は以下のとおりです。-jオプションは必須です（指定無しでも動かせますが、その場合Pythonファイル内に記述しているファイルを使用します）。

| option(full) | option(short) | required/default | description |
|--------|------|----|------|
|-jsonfile | -j | Required | 設定用JSONファイルのパス |
|-all | -a | False | すべてのORGを処理する|
|-divide | -d | False | ファイルをORGごとに分割して保存する|
|-recordsize | -r | 50 | APIで一度に取得するレコード数|

### コマンドラインサンプル
- python ts_get_user_list.py -j "credential_trial.json" -a -d -r 100
    - credential_trial.json という設定ファイルを使用
    - すべてのORGを処理します（設定ファイルがPrimaryOrgの場合）
    - ファイルをORGごとに分割して生成します
    - APIで一度に取得するレコード数を100にします
- python ts_get_user_list.py -j "credential_trial.json"
    - credential_trial.json という設定ファイルを使用
    - 所属ORGのみ処理します
    - ファイルはそれぞれひとかたまりで生成します
    - APIで一度に取得するレコード数は50にします
- python ts_get_user_list.py
    - 設定はすべてコードに書かれたデフォルト設定値で実行されます


## 作成されるファイル

本スクリプトにより以下のファイルが作成されます。

- ts_orglist_[credential_file_name].csv
- ts_usergrouplist_[credential_file_name].csv
- ts_userlist_[credential_file_name].csv

credential_file_name は、上述の通り読み込んだcredential.jsonファイル名のアンダーバーの後ろ部分から付与されます。
例えば「credential_orgname.json」であれば「orgname」となります。


例：credential_orgname.json

- ts_orglist_orgname.csv
- ts_usergrouplist_orgname.csv
- ts_userlist_orgname.csv

また、-dオプションをオンにすると、ORG名がさらに付与されます。


例：credential_orgname.json　でORGがOrg1、Org2とある場合

- ts_orglist_orgname.csv
- ts_usergrouplist_orgname_Primary.csv
- ts_usergrouplist_orgname_Org1.csv
- ts_usergrouplist_orgname_Org2.csv
- ts_userlist_orgname_Primary.csv
- ts_userlist_orgname_Org1.csv
- ts_userlist_orgname_Org2.csv


# VS Codeなどで直接実行する場合

本スクリプトはVS CODE上などで直接実行も可能です。設定値セクションにコマンドライン同等の設定があるので、ここを編集してください。

もしコマンドライン指定がない場合、ここで設定した値が使用されて実行されます。
