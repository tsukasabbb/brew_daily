# BREW DAILY - メール送信用の環境変数を一度だけ設定するスクリプト
#
# 使い方:
#   1. 下の4箇所の「ここに〜」の部分を、ご自分の実際の値に書き換えてください。
#   2. このファイルを保存します。
#   3. PowerShellでこのファイルがあるフォルダに移動し、次のように実行します:
#        powershell -ExecutionPolicy Bypass -File .\setup_mail_env.ps1
#      （または PowerShell 上で Set-ExecutionPolicy RemoteSigned -Scope CurrentUser を
#        一度実行してから .\setup_mail_env.ps1 と入力してもOKです）
#   4. 「設定完了」と表示されたら、今開いているPowerShellのウィンドウを閉じて、
#      新しく開き直してください（この操作をしないと新しい設定が反映されません）。
#   5. 以降は、brew_dailyフォルダで
#        python brew_magazine.py --mail-only
#      と打つだけで、毎回ここで入力し直さなくてもメール配信できるようになります。
#
# 注意: このファイルには実際のパスワードやトークンを書き込んだままにせず、
#       設定が終わったら書き換えた値を元の「ここに〜」に戻すか、
#       このファイル自体を削除することをおすすめします。

[Environment]::SetEnvironmentVariable("GMAIL_ADDRESS", "ここに自分のGmailアドレス", "User")
[Environment]::SetEnvironmentVariable("GMAIL_APP_PASSWORD", "ここにGoogleのアプリパスワード", "User")
[Environment]::SetEnvironmentVariable("WORKER_URL", "ここにCloudflare WorkerのURL（例: https://brew-daily.xxxx.workers.dev）", "User")
[Environment]::SetEnvironmentVariable("ADMIN_TOKEN", "ここに管理用トークン", "User")

Write-Host ""
Write-Host "設定完了。このPowerShellウィンドウを閉じて、新しく開き直してください。" -ForegroundColor Green
Write-Host "開き直した後、brew_dailyフォルダで python brew_magazine.py --mail-only を実行すれば配信されます。" -ForegroundColor Green
