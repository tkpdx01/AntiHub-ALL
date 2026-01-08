# AntiHook

<!--
AntiHook requires explicit configuration (no built-in defaults).
Run `antihook --config` once to set KIRO_SERVER_URL and BACKEND_URL.
-->

## 构建

```bash
# macOS
./build.sh darwin

# Windows
./build.sh windows

# Linux
./build.sh linux
```

## 开发

### 依赖安装

```bash
go mod download
```

### 编译

```bash
go build -o antihook .
```
### 使用

对于MacOS，使用前请先安装duti：

```bash
brew install duti
```

对于Windows，请运行AntiHook至少一次。

如果要移除Hook，请运行：
```bash
antihook --recover
```

## 配置

首次运行（直接运行 `antihook`，且终端可交互）会提示你输入 `KIRO_SERVER_URL` 和 `BACKEND_URL`（没有内置默认值，必须输入），并把配置写入用户目录下的 `config.json`；也可以选择写入用户环境变量。

优先级：环境变量 > 配置文件（未配置会提示你先配置）。

手动重新配置：

```bash
antihook --config
```

查看配置文件路径：

```bash
antihook --print-config-path
```


