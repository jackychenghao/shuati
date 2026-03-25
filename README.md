# 打卡题管理工具

自动从接龙管家采集每日打卡题，整理成 Word 文档一键打印。

## 使用流程

```
每天你做的：在微信群点开接龙题 → 收藏（5秒）

工具自动做：每天 7:00 同步新题入库

需要打印时：打开 localhost:8080 → 选日期 → 生成文档 → 打印
```

## 安装

```bash
pip install -r requirements.txt
python app.py
```

然后在浏览器打开 http://localhost:8080

## 首次登录

1. 打开工具后会跳转到登录页
2. 点击"打开接龙管家登录"，用微信扫码
3. 登录成功后，打开接龙管家页面的 F12 → Console，执行：
   ```
   localStorage.getItem("token")
   ```
4. 复制输出的 token，粘贴到弹窗中确认
5. 之后 token 自动保存，有效期约 3 天后自动提示重新登录

## 目录结构

```
math-collector/
├── app.py          # Flask 主程序（入口）
├── config.py       # 配置（端口、定时时间等）
├── auth.py         # 登录与 token 管理
├── database.py     # SQLite 数据库操作
├── jielong_api.py  # 接龙管家 API 调用
├── sync.py         # 同步引擎 + 定时任务
├── docgen.py       # Word 文档生成
├── templates/      # 网页模板
│   ├── index.html  # 主控制台
│   └── login.html  # 登录页
├── data/           # 运行时数据（自动创建）
│   ├── questions.db    # SQLite 数据库
│   ├── token.json      # 登录凭据
│   └── images/         # 下载的答案图片
└── requirements.txt
```

## 调整定时时间

编辑 `config.py`：
```python
SYNC_HOUR = 7    # 几点同步
SYNC_MINUTE = 0
```

## 手动触发同步

在控制台点"立即同步"，或命令行：
```bash
python sync.py
```
