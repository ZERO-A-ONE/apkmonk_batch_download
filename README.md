# apkmonk_batch_download
This is a script that allows you to download APKs in batches from apkmonk

这是一个工具可以让你从apkmonk这个网站中批量下载你所指定的APK中的所有已知版本

> 原脚本来自于Github用户：@senchen，本人主要工作在此基础上提供HTTP/2支持，以适应APKMONK的新传输格式

## 0x1 准备

需要安装以下一个库

```bash
pip3 install httpx[http2] httpx pandas lxml retrying
```

目前发现基于ARM处理器的机器无法正常安装lxml，也许后续可以通过自行编译安装完成

在meta-apk中的apk.csv文件中填写需要下载的APK名称

在脚本目录下新建一个logFiles文件夹

## 0x2 使用

如果直接在外网的VPS进行运行，直接：

```bash
python3 apk_apkmonk_download.py
```

如果需要在本机使用代理请修改http2.py中的代理配置后执行：

```bash
python3 http2.py
```

之后可在apks文件中查看下载完成的APK文件

> 可以自行修改线程数提高下载效率
