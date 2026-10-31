/**
 * @local/dsh-video-panel — host half（手写 ESM，无构建步骤）。
 *
 * 右侧栏「视频时间轴」面板的数据接口：
 *   GET /video-panel/api?action=list
 *   GET /video-panel/api?action=detail&video_id=...
 *   GET /video-panel/api?action=read&video_id=...&t0=..&t1=..&frames=4
 *   GET /video-panel/api?action=search&video_id=...&query=...
 *   GET /video-panel/api?action=danmaku&video_id=...&t0=..&t1=..
 *   GET /video-panel/api?action=delete&video_id=...   （删除该视频缓存）
 *   GET /video-panel/api?action=clear                 （清空所有视频缓存）
 *   POST /video-panel/api?action=ask  {session_id, text}（把一段提示发进当前会话，驱动 agent）
 *   GET /video-panel/frame?path=<cache 内 PNG 绝对路径>
 *
 * 所有数据都通过 `python -m vidx.panel_api` 调 engine 的 pipeline，
 * 不在 Node 里重复实现检索/重分段/词级锚点逻辑。
 */
import { execFile } from 'node:child_process'
import { createReadStream, existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'

const run = promisify(execFile)

export const name = '@local/dsh-video-panel'
export const inject = ['webServer', 'workingDirectory', 'agents']

const PREFIX = '/video-panel'
const PKG_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const REPO_ROOT = path.resolve(PKG_ROOT, '..')
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

/** 定位 repo/engine/python/cache：支持“repo 根=dsh-video-panel 的上一级”与“workspace 布局”。 */
function resolvePaths(ctx) {
  const home = (ctx.workingDirectory && ctx.workingDirectory.defaultDirectory) || process.cwd()
  const roots = [
    process.env.VIDX_REPO,
    REPO_ROOT,
    path.resolve(PKG_ROOT, '../..'),
    home,
    process.cwd(),
  ].filter(Boolean)
  let root = ''
  for (const cand of roots) {
    try {
      if (existsSync(path.join(cand, 'engine', 'vidx'))
          || existsSync(path.join(cand, 'video-plugin', 'engine', 'vidx'))) {
        root = cand
        break
      }
    } catch {
      /* ignore */
    }
  }
  root = root || REPO_ROOT
  const engineDir = existsSync(path.join(root, 'engine', 'vidx'))
    ? path.join(root, 'engine')
    : path.join(root, 'video-plugin', 'engine')
  const venvDir = IS_WIN ? 'Scripts' : 'bin'
  const pyName = IS_WIN ? 'python.exe' : 'python'
  const pythonPath = process.env.VIDX_PYTHON || firstExisting([
    path.join(root, '.venv', venvDir, pyName),
    path.join(root, 'french-demo', '.venv', venvDir, pyName),
    path.join(root, '..', 'french-demo', '.venv', venvDir, pyName),
  ])
  const cacheDir = process.env.VIDX_CACHE || firstExisting([
    path.join(root, '_video_cache'),
    path.join(root, '..', '_video_cache'),
  ]) || path.join(root, '_video_cache')
  return { workspace: root, engineDir, pythonPath, cacheDir }
}

/** 从运行中的 DSH runtime 里加载 @deepseek-ai/dsh-llm（只为 createUserMessage）。 */
let llmModule
function loadLlm() {
  if (llmModule) return llmModule
  const argv1 = process.argv[1] ? path.resolve(process.argv[1]) : ''
  const runtimeRoot = argv1 ? path.resolve(path.dirname(argv1), '../../../..') : ''
  const anchors = [
    path.join(runtimeRoot, 'node_modules', '@deepseek-ai', 'dsh-agent-loop', 'lib', 'index.js'),
    path.join(runtimeRoot, 'node_modules', '@deepseek-ai', 'dsh-llm', 'lib', 'index.js'),
  ]
  for (const anchor of anchors) {
    try {
      if (!existsSync(anchor)) continue
      const req = createRequire(anchor)
      llmModule = req('@deepseek-ai/dsh-llm')
      if (llmModule && typeof llmModule.createUserMessage === 'function') return llmModule
    } catch {}
  }
  throw new Error('无法从 DSH runtime 加载 @deepseek-ai/dsh-llm（createUserMessage）')
}

function readBody(req, limit = 256 * 1024) {
  return new Promise((resolve, reject) => {
    let size = 0
    const chunks = []
    req.on('data', (chunk) => {
      size += chunk.length
      if (size > limit) {
        reject(new Error('body too large'))
        req.destroy()
        return
      }
      chunks.push(chunk)
    })
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')))
    req.on('error', reject)
  })
}

export function apply(ctx) {
  const { workspace, engineDir, pythonPath, cacheDir } = resolvePaths(ctx)

  const callPython = async (action, args) => {
    const { stdout } = await run(
      pythonPath,
      ['-m', 'vidx.panel_api', action, JSON.stringify(args)],
      {
        cwd: engineDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
        maxBuffer: 32 * 1024 * 1024,
        timeout: 120000,
        windowsHide: true,
      },
    )
    const line = String(stdout).trim().split('\n').filter(Boolean).pop() || '{}'
    const parsed = JSON.parse(line)
    if (parsed && parsed.error && !parsed.items && !parsed.hits && !parsed.sections) {
      throw new Error(parsed.error)
    }
    return parsed
  }

  const frameUrl = (file) => {
    if (typeof file !== 'string' || !file) return undefined
    return `${PREFIX}/frame?path=${encodeURIComponent(file)}`
  }

  const decorate = (payload) => {
    if (Array.isArray(payload.frames)) {
      payload.frames = payload.frames.map((f) => {
        const url = frameUrl(f.file)
        const out = { t: f.t, reused: f.reused }
        if (url) out.url = url
        return out
      })
    }
    return payload
  }

  const sendJson = (res, status, data) => {
    const body = JSON.stringify(data)
    res.writeHead(status, {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'content-length': Buffer.byteLength(body),
    })
    res.end(body)
  }

  const serveFrame = async (req, res, url) => {
    const file = url.searchParams.get('path') || ''
    const resolved = path.resolve(file)
    const root = path.resolve(cacheDir)
    if (!resolved.startsWith(root + path.sep) || !resolved.toLowerCase().endsWith('.png')) {
      sendJson(res, 403, { error: 'forbidden frame path' })
      return
    }
    try {
      await new Promise((resolve, reject) => {
        const stream = createReadStream(resolved)
        stream.on('error', reject)
        stream.on('open', () => {
          res.writeHead(200, { 'content-type': 'image/png', 'cache-control': 'max-age=600' })
          stream.pipe(res)
          stream.on('end', resolve)
        })
        req.on('close', () => { stream.destroy(); resolve() })
      })
    } catch (err) {
      if (!res.headersSent) sendJson(res, 404, { error: `frame not found: ${String(err)}` })
      else res.end()
    }
  }

  ctx.effect(() => ctx.webServer.register({
    kind: 'prefix',
    path: PREFIX,
    handler: async (req, res) => {
      try {
        const url = new URL(String(req.url || '/'), 'http://localhost')
        if (url.pathname === `${PREFIX}/frame`) {
          await serveFrame(req, res, url)
          return
        }
        if (url.pathname !== `${PREFIX}/api`) {
          sendJson(res, 404, { error: 'not found' })
          return
        }
        const action = url.searchParams.get('action') || 'list'
        if (action === 'where') {
          sendJson(res, 200, {
            workspace, engineDir, pythonPath, cacheDir,
            cwd: process.cwd(),
            defaultDirectory: ctx.workingDirectory.defaultDirectory,
            engineExists: existsSync(engineDir),
            pythonExists: existsSync(pythonPath),
          })
          return
        }
        if (action === 'list') {
          sendJson(res, 200, await callPython('list', {}))
          return
        }
        if (action === 'clear') {
          sendJson(res, 200, await callPython('clear', {}))
          return
        }
        if (action === 'ask') {
          if (req.method !== 'POST') {
            sendJson(res, 405, { error: 'action=ask 需要 POST' })
            return
          }
          const payload = JSON.parse(await readBody(req) || '{}')
          const sessionId = String(payload.session_id || '')
          const text = String(payload.text || '').slice(0, 6000)
          if (!sessionId || !text.trim()) {
            sendJson(res, 400, { error: 'session_id 和 text 必填' })
            return
          }
          const agent = ctx.agents.get(sessionId)
          if (!agent) {
            sendJson(res, 404, { error: `没有找到会话 agent: ${sessionId}` })
            return
          }
          const { createUserMessage } = loadLlm()
          agent.followup(createUserMessage({
            content: [{ type: 'text', text }],
            source: { kind: 'user' },
          }))
          sendJson(res, 200, { ok: true, session_id: sessionId, status: agent.status })
          return
        }
        const videoId = url.searchParams.get('video_id') || ''
        if (action === 'delete') {
          if (!videoId) {
            sendJson(res, 400, { error: 'video_id required' })
            return
          }
          sendJson(res, 200, await callPython('delete', { video_id: videoId }))
          return
        }
        if (!videoId) {
          sendJson(res, 400, { error: 'video_id required' })
          return
        }
        if (action === 'detail') {
          sendJson(res, 200, decorate(await callPython('detail', { video_id: videoId })))
          return
        }
        if (action === 'read') {
          const t0 = Number(url.searchParams.get('t0') || 0)
          const t1 = Number(url.searchParams.get('t1') || t0 + 30)
          const frames = Number(url.searchParams.get('frames') || 4)
          sendJson(res, 200, decorate(await callPython('read', { video_id: videoId, t0, t1, frames })))
          return
        }
        if (action === 'search') {
          const query = url.searchParams.get('query') || ''
          const k = Number(url.searchParams.get('k') || 8)
          sendJson(res, 200, await callPython('search', { video_id: videoId, query, k }))
          return
        }
        if (action === 'danmaku') {
          const t0 = Number(url.searchParams.get('t0') || 0)
          const t1 = Number(url.searchParams.get('t1') || t0 + 60)
          const k = Number(url.searchParams.get('k') || 20)
          sendJson(res, 200, await callPython('danmaku', { video_id: videoId, t0, t1, k }))
          return
        }
        sendJson(res, 400, { error: `unknown action: ${action}` })
      } catch (err) {
        sendJson(res, 500, { error: `${err && err.name ? err.name : 'Error'}: ${err && err.message ? err.message : err}` })
      }
    },
  }), 'dsh-video-panel: api route')
}
