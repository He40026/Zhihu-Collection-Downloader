# 知乎收藏下载器 Zhihu-Collection-Downloader

📂 将多个知乎收藏夹中的回答、文章、想法等内容批量下载为 Markdown 文件，并自动保存图片到本地

## 功能特性

- 📂**多收藏夹支持**：通过配置json文件批量下载多个收藏夹内容
- 🖼️**图片本地化**：下载图片到本地，离线也能看
- 🔍**智能去重**：基于文章URL和修改时间判断内容更新，避免重复下载
- 📄**多类型支持**：兼容回答、文章、想法、视频等多种知乎内容格式

## 快速开始🚀

### 安装步骤⚙️

1.**克隆仓库**

```bash
git clone https://github.com/He40026/Zhihu-Collection-Downloader.git
cd Zhihu-Collection-Downloader
```

2.**安装依赖**

```bash
pip install -r requirements.txt
```

### 配置json文件🔧

1.**配置cookies**

1. 登录知乎网页版，按F12打开开发者工具

2. 访问任意页面，在「Network」选项卡复制请求的cURL命令

3. 使用 curlconverter.com 转换为JSON格式

4. 将结果按示例格式保存为 `Cookies.json`

示例格式：

```json
{
    "_zap": "根据实际获取的cookies填写，下同",
    "d_c0": "",
    "_xsrf": "",
    "q_c1": "",
    "edu_user_uuid": "",
    "Hm_lvt_xxxxxxxxxxxxxxxxx": "",
    "z_c0": "",
    "__zse_ck": "",
    "tst": "",
    "BEC": "",
    "SESSIONID": ""
}
```

2.**配置收藏夹路径**

将图片保存路径、收藏夹链接及保存路径按示例格式保存为 `url.json`
示例格式：

```json
{
    "global_image_path": "./images",
    "collections": [
        {
            "url": "https://www.zhihu.com/collection/收藏夹id1",
            "path": "./docs/收藏夹1"
        },
        {
            "url": "https://www.zhihu.com/collection/收藏夹id2",
            "path": "./docs/收藏夹2"
        }
    ]
}
```

- `global_image_path`: 全局图片存储目录
- `collections`: 收藏夹列表，每个条目包含：
  - `url`: 收藏夹URL
  - `path`: Markdown文件保存路径

### 运行程序▶️

```bash
python main.py
```

程序运行后：

1. 自动创建文件夹
2. 下载内容并保存为 `标题.md`
3. 图片保存到全局图片存储目录
4. 自动跳过已存在的相同内容
5. 不相同重名内容自动添加后缀序号

## 注意事项❓

- 长期使用需要更新Cookies

## 更新日志📜

### 2025.5.14

**创建新项目**：[Zhihu-Collection-Downloader](https://github.com/He40026/Zhihu-Collection-Downloader)

1.将图片保存方式由链接改为本地保存

2.增加了文件头部参数

3.修改了排重机制，不再使用哈希值，而是通过文章url和最后修改时间排重

4.优化代码结构，增强健壮性

### 2025.4.10

**创建原项目分支**：[He40026/ZhiHu-Collection-To-Markdown](https://github.com/He40026/ZhiHu-Collection-To-Markdown)

1.新增批量下载收藏夹内容，读取url.json获取收藏夹链接及保存路径，以下载多个收藏夹内容

2.新增验证文件重复功能，同名同哈希值文章将跳过下载

3.修改文件命名规则

## 关于本项目ℹ️

本项目基于 [zanghuaren/ZhiHu-Collection-To-Markdown](https://github.com/zanghuaren/ZhiHu-Collection-To-Markdown)二次开发

在此感谢原作者zanghuaren

## 免责声明⚠️

- 本项目仅供个人学习和技术研究
- 使用过程中务必遵守相关协议及法律法规
- 开发者不承担因使用者滥用导致的任何法律责任
