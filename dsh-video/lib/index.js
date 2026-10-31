/**
 * @local/dsh-video — bind the local vidx video-reading engine into DSH.
 *
 * 本插件只做一件事：确保官方 `@deepseek-ai/dsh-mcp-client` 有一条指向本地
 * Python vidx MCP server（stdio）的桥接条目。工具以 `mcp__video__<name>` 暴露：
 *   open / index / status / outline / read / search / transcript
 *
 * 为什么不重写 MCP：`@deepseek-ai/dsh-mcp-client` 已负责协议、图片块投影、
 * 重连与超时；Python 侧（vidx）负责 ffmpeg / faster-whisper / 检索。
 *
 * Config（均可选，默认值针对本机工作区）：
 *   engineDir         vidx Python 包所在目录（默认 …/harness/video-plugin/engine）
 *   pythonPath        启动 MCP server 的解释器（默认 frdemo venv，含 faster-whisper）
 *   serverName        MCP 命名空间，工具名 mcp__<serverName>__<tool>
 *   toolCallTimeoutMs 单次调用超时（read 含抽帧，慢一点）
 *   cacheDir / ffmpegPath / modelDir  透传给 Python（VIDX_* 环境变量）
 *   autoLoad          false = 不注册，保持惰性
 */
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = '@local/dsh-video'

/** The loader service is required; without it there is nothing to bind. */
export const inject = ['loader']

const MCP_CLIENT_PLUGIN = '@deepseek-ai/dsh-mcp-client'

const PKG_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const REPO_ROOT = path.resolve(PKG_ROOT, '..') // repo layout: <repo>/dsh-video/lib
const IS_WIN = process.platform === 'win32'

function firstExisting(cands) {
  for (const cand of cands) {
    try {
      if (cand && existsSync(cand)) return cand
    } catch {
      /* ignore */
    }
  }
  return ''
}

function detectDefaults() {
  const engineDir = firstExisting([
    path.join(REPO_ROOT, 'engine'),
    path.join(REPO_ROOT, 'video-plugin', 'engine'),
  ]) || path.join(REPO_ROOT, 'engine')
  const pythonCands = IS_WIN
    ? [path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe'),
       path.join(REPO_ROOT, '..', 'french-demo', '.venv', 'Scripts', 'python.exe')]
    : [path.join(REPO_ROOT, '.venv', 'bin', 'python'),
       path.join(REPO_ROOT, '..', 'french-demo', '.venv', 'bin', 'python')]
  const cacheDir = firstExisting([
    path.join(REPO_ROOT, '_video_cache'),
    path.join(REPO_ROOT, '..', '_video_cache'),
  ])
  const ffmpegName = IS_WIN ? 'ffmpeg.exe' : 'ffmpeg'
  const ffmpegPath = firstExisting([
    path.join(REPO_ROOT, '_work', 'bin', ffmpegName),
    path.join(REPO_ROOT, '..', '_work', 'bin', ffmpegName),
  ])
  const modelDir = firstExisting([
    path.join(REPO_ROOT, 'models', 'faster-whisper-large-v3-turbo'),
    path.join(REPO_ROOT, '..', 'french-demo', 'models', 'faster-whisper-large-v3-turbo'),
  ])
  return {
    engineDir,
    pythonPath: process.env.VIDX_PYTHON || firstExisting(pythonCands),
    serverName: 'video',
    toolCallTimeoutMs: 180_000,
    cacheDir: process.env.VIDX_CACHE || cacheDir,
    ffmpegPath: process.env.VIDX_FFMPEG || ffmpegPath,
    modelDir: process.env.VIDX_MODEL_DIR || modelDir,
    autoLoad: true,
  }
}

const DEFAULTS = detectDefaults()

export function apply(ctx, config = {}) {
  const cfg = { ...DEFAULTS, ...(config || {}) }
  const serverName = String(cfg.serverName || 'video')
  const engineDir = String(cfg.engineDir || DEFAULTS.engineDir).replace(/\/+$/, '')
  const pythonPath = String(cfg.pythonPath || DEFAULTS.pythonPath)

  const log = (level, message) => {
    try {
      ctx.logger?.[level]?.(message)
    } catch {
      /* logging must never break activation */
    }
  }

  if (cfg.autoLoad === false) {
    log('info', '[dsh-video] autoLoad=false，未注册视频桥接')
    return
  }
  if (!ctx.loader) {
    log('warn', '[dsh-video] loader 服务不可用，无法注册视频桥接')
    return
  }
  if (!existsSync(pythonPath)) {
    log('warn', `[dsh-video] 找不到解释器 ${pythonPath}；视频工具将不可用（可用 config.pythonPath 覆盖）`)
  }

  const mcpConfig = () => ({
    serverName,
    transport: 'stdio',
    command: pythonPath,
    args: ['-m', 'vidx.mcp_server'],
    cwd: engineDir,
    env: {
      PYTHONPATH: engineDir,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUNBUFFERED: '1',
      ...(cfg.cacheDir ? { VIDX_CACHE: String(cfg.cacheDir) } : {}),
      ...(cfg.ffmpegPath ? { VIDX_FFMPEG: String(cfg.ffmpegPath) } : {}),
      ...(cfg.modelDir ? { VIDX_MODEL_DIR: String(cfg.modelDir) } : {}),
    },
    toolCallTimeoutMs: Number(cfg.toolCallTimeoutMs || DEFAULTS.toolCallTimeoutMs),
    // 缺失/异常不阻断 DSH 启动；首次调用工具时才真正连 Python。
    failOnStartupError: false,
    reconnect: {
      enabled: true,
      initialDelayMs: 1000,
      maxDelayMs: 30_000,
      maxAttempts: 10,
    },
  })

  /** 已装配的同名桥接条目（幂等，避免重复 serverName 预约）。 */
  const findEntry = () => {
    for (const entry of ctx.loader.entries()) {
      const options = entry?.options ?? {}
      if (options.group) continue
      if (!String(options.name ?? '').includes('dsh-mcp-client')) continue
      if (options.config?.serverName === serverName) return entry
    }
    return undefined
  }

  let createdEntry
  const ensureBridge = async () => {
    if (findEntry()) {
      log('info', `[dsh-video] MCP 桥接条目已存在（serverName=${serverName}），无需重复创建`)
      return
    }
    try {
      createdEntry = await ctx.loader.create({ name: MCP_CLIENT_PLUGIN, config: mcpConfig() })
      log('info', `[dsh-video] 已创建 MCP 桥接：${MCP_CLIENT_PLUGIN} (serverName=${serverName}, cwd=${engineDir})`)
    } catch (error) {
      log('warn', `[dsh-video] 创建 MCP 桥接失败：${error?.stack ?? error}`)
    }
  }

  // 延后一个 tick：apply() 内同步 loader.create 会在 loader 装配期间重入。
  const timer = setTimeout(() => {
    void ensureBridge()
  }, 0)

  ctx.effect(() => () => {
    clearTimeout(timer)
    const entry = createdEntry
    createdEntry = undefined
    if (!entry) return
    try {
      entry._dispose?.()
      log('info', `[dsh-video] 已释放自建的 MCP 桥接（serverName=${serverName}）`)
    } catch (error) {
      log('warn', `[dsh-video] 释放 MCP 桥接失败：${error?.message ?? error}`)
    }
  }, 'dsh-video: own the video MCP bridge entry')
}
