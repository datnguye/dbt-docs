# Terminal half of docs/assets/img/dbt-2-info-schema.gif — run via record.sh,
# which exports DEMO (the jaffle-shop dbt project), REPO and DBT_DIR (dbt Fusion),
# and cds into a work dir.
Output terminal.mp4

Set Shell "bash"
Set FontSize 16
Set Width 1280
Set Height 720
Set Padding 24
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 40ms

Hide
Type 'cd "$DEMO" && export PATH="$DBT_DIR:$PATH" DBT_PROFILES_DIR="$DEMO" DBT_LOG_FORMAT=text && dbdocs() { "$REPO/.venv/bin/dbdocs" "$@"; } && export PS1="\[\e[1;36m\]jaffle_shop\[\e[0m\] $ " && clear'
Enter
Show

Sleep 600ms
Type "dbt build --generate-info-schema --static-analysis strict"
Enter
Wait+Line@90s /jaffle_shop \$/
Sleep 3s

Type "clear"
Enter
Type "ls target/info_schema/v1 | head -5"
Enter
Sleep 2s

Type "cat dbdocs.yml"
Enter
Sleep 2.5s

Type "dbdocs generate"
Enter
Wait+Screen@30s /Generated site/
Sleep 3s

Type "dbdocs serve"
Enter
Wait+Screen@15s /Serving/
Sleep 3s
Ctrl+C
Sleep 600ms
