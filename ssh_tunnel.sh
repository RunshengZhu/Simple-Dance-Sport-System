#!/bin/bash
# SSH隧道脚本：将服务器端口转发到本地

SERVER="sport-coder@59.110.90.21"
LOCAL_PORT=8080
REMOTE_PORT=80

echo "建立SSH隧道: localhost:$LOCAL_PORT -> $SERVER:$REMOTE_PORT"
ssh -L $LOCAL_PORT:localhost:$REMOTE_PORT -N -f $SERVER

if [ $? -eq 0 ]; then
    echo "✅ SSH隧道建立成功"
    echo "现在可以访问: http://localhost:$LOCAL_PORT"
else
    echo "❌ SSH隧道建立失败"
fi
