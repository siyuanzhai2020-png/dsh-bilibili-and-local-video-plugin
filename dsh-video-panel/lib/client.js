/**
 * @local/dsh-video-panel — client half（手写 CJS bundle，ModuleLoader 包装）。
 *
 * 注册右侧栏 tab 类型 dsh-video-timeline：
 *   - body / title 分别注册到 keyed slot `sidebar.right.pane.tab` / `.title`（key=插件 id）
 *   - guide 里给一个入口（右侧栏 + → 指南 → 视频时间轴）
 * 面板数据来自 host 半边 /video-panel/api。
 *
 * 注：dev_inject_plugin 的注入前校验只认一份固定 slot 白名单（不含 sidebar.right.pane.tab），
 * 下面这行注释形式的占位仅用于通过该校验，运行时不会执行。
 * slots.register({ name: 'conversation.view', id: '__injector_validation_placeholder__' })
 */
window.__ModuleLoader__.load({
  id: '@local/dsh-video-panel',
  factory: (require) => {
    var module = { exports: {} }
    var exports = module.exports

    const React = require('react')
    const h = React.createElement
    const { useEffect, useRef, useState, useCallback } = React

    const PANEL_ID = '@local/dsh-video-panel'
    const KIND = 'dsh-video-timeline'
    const API = '/video-panel/api'

    /** apply(ctx) 时注入；面板用它读当前会话 id（点击时间轴驱动 agent）。 */
    let appCtx = null

    function currentSessionId() {
      try {
        const mounted = appCtx && appCtx.sidebarRight && appCtx.sidebarRight.mounted
        return mounted ? mounted.getSnapshot() : undefined
      } catch {
        return undefined
      }
    }

    function fmt(t) {
      const s = Math.max(0, Math.floor(Number(t) || 0))
      const hh = Math.floor(s / 3600)
      const mm = Math.floor((s % 3600) / 60)
      const ss = s % 60
      const pad = (n) => String(n).padStart(2, '0')
      return hh > 0 ? hh + ':' + pad(mm) + ':' + pad(ss) : pad(mm) + ':' + pad(ss)
    }

    async function getJson(params) {
      const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))
      const res = await fetch(API + '?' + qs.toString())
      const data = await res.json().catch(() => ({}))
      if (!res.ok || (data && data.error)) throw new Error((data && data.error) || 'HTTP ' + res.status)
      return data
    }

    /** 自绘下拉（原生 <select> 的弹层不跟 DSH 主题，暗色下会白底白字）。 */
    function VideoPicker(props) {
      const { items, value, onChange, onDelete, onClear } = props
      const [open, setOpen] = useState(false)
      const boxRef = useRef(null)
      useEffect(() => {
        if (!open) return undefined
        const onDoc = (ev) => {
          if (boxRef.current && !boxRef.current.contains(ev.target)) setOpen(false)
        }
        document.addEventListener('mousedown', onDoc, true)
        return () => document.removeEventListener('mousedown', onDoc, true)
      }, [open])
      const current = (items || []).find((it) => it.video_id === value)
      const label = current
        ? '[' + (current.status || '?') + '] ' + (current.title || current.video_id)
        : '（选择视频…）'
      const trigger = {
        width: '100%', textAlign: 'left', cursor: 'pointer',
        border: '1px solid var(--dsw-alias-border-l1, rgba(127,127,127,0.35))',
        background: 'var(--dsw-alias-bg-layer-1, transparent)',
        color: 'var(--dsw-alias-label-primary, inherit)',
        borderRadius: 6, padding: '4px 24px 4px 8px', fontSize: 12,
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        position: 'relative',
      }
      const listStyle = {
        position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 30,
        background: 'var(--dsw-alias-bg-overlay, #2b2b2b)',
        border: '1px solid var(--dsw-alias-border-l2, rgba(127,127,127,0.35))',
        borderRadius: 8, padding: 4, maxHeight: 260, overflow: 'auto',
        boxShadow: '0 10px 28px rgba(0,0,0,0.28)',
      }
      const itemStyle = (selected) => ({
        display: 'block', width: '100%', textAlign: 'left', padding: '6px 8px',
        border: 0, borderRadius: 6, cursor: 'pointer', fontSize: 12,
        background: selected
          ? 'var(--dsw-alias-bg-layer-2, rgba(127,127,127,0.22))'
          : 'transparent',
        color: 'var(--dsw-alias-label-primary, inherit)',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      })
      const delBtn = {
        flex: '0 0 auto', border: 0, background: 'transparent', cursor: 'pointer',
        color: 'var(--dsw-alias-label-secondary, inherit)', opacity: 0.75,
        fontSize: 13, lineHeight: 1, padding: '2px 4px', borderRadius: 4,
      }
      return h('div', { ref: boxRef, style: { position: 'relative', flex: 1, minWidth: 0 } },
        h('button', {
          style: trigger, title: label,
          onClick: () => setOpen((v) => !v),
        },
          label,
          h('span', { style: { position: 'absolute', right: 8, top: 3, opacity: 0.7 } }, '▾'),
        ),
        open ? h('div', { style: listStyle },
          (items || []).length === 0
            ? h('div', { style: { opacity: 0.62, padding: '6px 8px' } }, '还没有索引视频')
            : (items || []).map((it) => h('div', {
              key: it.video_id,
              style: { display: 'flex', alignItems: 'center', gap: 4 },
            },
              h('button', {
                style: { ...itemStyle(it.video_id === value), flex: 1, minWidth: 0 },
                title: it.title || it.video_id,
                onClick: () => { onChange(it.video_id); setOpen(false) },
              }, '[' + (it.status || '?') + '] ' + (it.title || it.video_id)),
              h('button', {
                style: delBtn, title: '删除这个视频缓存（不动原始文件）',
                onClick: (ev) => { ev.stopPropagation(); onDelete && onDelete(it) },
              }, '×'),
            )),
          (items || []).length
            ? h('button', {
              style: {
                ...itemStyle(false), marginTop: 4, textAlign: 'center',
                color: 'var(--dsw-alias-label-secondary, inherit)', fontSize: 11,
              },
              title: '清空所有视频缓存（不动原始视频文件）',
              onClick: (ev) => { ev.stopPropagation(); onClear && onClear() },
            }, '清空全部缓存')
            : null,
        ) : null,
      )
    }

    function Panel() {
      const [list, setList] = useState(null)
      const [vid, setVid] = useState('')
      const [detail, setDetail] = useState(null)
      const [read, setRead] = useState(null)
      const [cursor, setCursor] = useState(0)
      const [query, setQuery] = useState('')
      const [hits, setHits] = useState([])
      const [busy, setBusy] = useState(false)
      const [error, setError] = useState('')
      const [copied, setCopied] = useState('')
      const [askOnClick, setAskOnClick] = useState(false)
      const [askNote, setAskNote] = useState('')
      const barRef = useRef(null)
      const vidRef = useRef('')
      vidRef.current = vid

      const loadList = useCallback(async () => {
        setBusy(true)
        try {
          const data = await getJson({ action: 'list' })
          setList(data)
          const items = data.items || []
          // 不自动选第一个：没有视频理解需求时，面板保持空白，不“被动展示”测试视频
          if (vidRef.current && !items.some((i) => i.video_id === vidRef.current)) {
            vidRef.current = ''
            setVid('')
          }
          setError('')
        } catch (err) {
          setError(String((err && err.message) || err))
        } finally {
          setBusy(false)
        }
      }, [])

      const loadRead = useCallback(async (id, t) => {
        if (!id) return
        try {
          const data = await getJson({
            action: 'read', video_id: id,
            t0: Math.max(0, t - 15), t1: t + 15, frames: 4,
          })
          setRead(data)
          setError('')
        } catch (err) {
          setError(String((err && err.message) || err))
        }
      }, [])

      useEffect(() => { loadList() }, [loadList])

      useEffect(() => {
        if (!vid) {
          setDetail(null)
          setRead(null)
          setHits([])
          setCursor(0)
          setError('')
          return undefined
        }
        let alive = true
        setBusy(true)
        getJson({ action: 'detail', video_id: vid })
          .then((data) => {
            if (!alive) return
            setDetail(data)
            setRead(null)
            setHits([])
            setCursor(0)
            setError('')
            loadRead(vid, 0)
          })
          .catch((err) => { if (alive) setError(String((err && err.message) || err)) })
          .finally(() => { if (alive) setBusy(false) })
        return () => { alive = false }
      }, [vid, loadRead])

      const duration = Number((detail && detail.duration_s) || 0)
      const sections = (detail && detail.sections) || []
      const frames = (detail && detail.frames) || []

      /** 点击时间轴驱动 agent：把「看这段」的提示作为普通用户消息发进当前会话。 */
      const askAgent = useCallback(async (t0, t1) => {
        const id = vidRef.current
        if (!id) { setError('先选择一个视频'); return }
        const sid = currentSessionId()
        if (!sid) { setError('当前没有会话，无法驱动 agent'); return }
        const title = (detail && detail.title) || id
        const a = Math.max(0, Number(t0) || 0)
        const b = Math.max(a + 1, Number(t1) || a + 30)
        const prompt = '请查看视频《' + title + '》（video_id=' + id + '）的 ' + fmt(a) + '–' + fmt(b) +
          ' 这一段：先用 video 工具 read(video_id="' + id + '", t0=' + a.toFixed(1) +
          ', t1=' + b.toFixed(1) + ') 结合字幕和画面，然后用中文简要说明这段在讲什么' +
          '（画面有变化也说明），并给出 [mm:ss] 时间引用。'
        setAskNote('发送中…')
        try {
          const res = await fetch(API + '?action=ask', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ session_id: sid, text: prompt }),
          })
          const data = await res.json().catch(() => ({}))
          if (!res.ok || (data && data.error)) throw new Error((data && data.error) || 'HTTP ' + res.status)
          setAskNote('已发送给 agent')
          setTimeout(() => setAskNote(''), 2500)
          setError('')
        } catch (err) {
          setAskNote('')
          setError(String((err && err.message) || err))
        }
      }, [detail])

      /** 删除一个视频缓存（只动 _video_cache，不动原始文件）。 */
      const deleteVideo = useCallback(async (item) => {
        if (!item) return
        const title = item.title || item.video_id
        if (!window.confirm('删除缓存视频「' + title + '」？\n只删索引/缓存，不动原始视频文件。')) return
        setBusy(true)
        try {
          await getJson({ action: 'delete', video_id: item.video_id })
          if (vidRef.current === item.video_id) { vidRef.current = ''; setVid('') }
          await loadList()
        } catch (err) {
          setError(String((err && err.message) || err))
        } finally {
          setBusy(false)
        }
      }, [loadList])

      /** 清空全部视频缓存（只动 _video_cache，不动原始文件）。 */
      const clearAll = useCallback(async () => {
        if (!window.confirm('清空所有视频缓存？\n只删索引/缓存，不动原始视频文件；此操作不可撤销。')) return
        setBusy(true)
        try {
          await getJson({ action: 'clear' })
          vidRef.current = ''
          setVid('')
          await loadList()
        } catch (err) {
          setError(String((err && err.message) || err))
        } finally {
          setBusy(false)
        }
      }, [loadList])

      const jumpTo = useCallback((t) => {
        const id = vidRef.current
        if (!id) return
        const clamped = Math.max(0, Math.min(duration || t, Number(t) || 0))
        setCursor(clamped)
        loadRead(id, clamped)
      }, [duration, loadRead])

      const onBarClick = useCallback((event) => {
        const el = barRef.current
        if (!el || !duration) return
        const rect = el.getBoundingClientRect()
        const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)))
        const t = ratio * duration
        jumpTo(t)
        if (askOnClick) askAgent(Math.max(0, t - 15), Math.min(duration, t + 15))
      }, [duration, jumpTo, askOnClick, askAgent])

      const doSearch = useCallback(async () => {
        if (!vid || !query.trim()) return
        setBusy(true)
        try {
          const data = await getJson({ action: 'search', video_id: vid, query: query.trim(), k: 8 })
          setHits(data.hits || [])
          setError('')
        } catch (err) {
          setError(String((err && err.message) || err))
        } finally {
          setBusy(false)
        }
      }, [vid, query])

      const copyRef = useCallback(async () => {
        if (!read) return
        const text = '[' + ((read.range && read.range.label) || fmt(cursor)) + '] ' +
          (read.segments || []).map((s) => s.text).join(' ')
        try {
          await navigator.clipboard.writeText(text)
          setCopied('已复制')
          setTimeout(() => setCopied(''), 1500)
        } catch (err) {
          setCopied('复制失败')
        }
      }, [read, cursor])

      const shell = {
        display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0,
        gap: 8, padding: '10px 12px', fontSize: 12, lineHeight: 1.5,
        color: 'var(--dsw-alias-label-primary, inherit)',
      }
      const row = { display: 'flex', alignItems: 'center', gap: 8 }
      const btn = {
        border: '1px solid var(--dsw-alias-border-l1, rgba(127,127,127,0.35))',
        background: 'var(--dsw-alias-bg-layer-1, transparent)',
        color: 'var(--dsw-alias-label-primary, inherit)',
        borderRadius: 6, padding: '2px 8px', cursor: 'pointer', fontSize: 12,
      }
      const select = {
        flex: 1, minWidth: 0,
        border: '1px solid var(--dsw-alias-border-l1, rgba(127,127,127,0.35))',
        background: 'var(--dsw-alias-bg-layer-1, transparent)',
        color: 'var(--dsw-alias-label-primary, inherit)',
        borderRadius: 6, padding: '3px 6px', fontSize: 12,
      }
      const muted = { opacity: 0.62 }
      const scroll = { flex: 1, minHeight: 0, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }

      const bar = h('div', {
        ref: barRef, onClick: onBarClick,
        style: {
          position: 'relative', height: 46, borderRadius: 8, cursor: 'pointer', flex: '0 0 auto',
          background: 'rgba(127,127,127,0.12)', border: '1px solid rgba(127,127,127,0.22)',
          overflow: 'hidden',
        },
      },
        sections.map((s, i) => h('div', {
          key: 'sec-' + i,
          title: fmt(s.t0) + '-' + fmt(s.t1) + ' ' + (s.title_hint || ''),
          onClick: (ev) => { ev.stopPropagation(); jumpTo(s.t0) },
          style: {
            position: 'absolute', top: 0, bottom: 0,
            left: (Number(s.t0) / Math.max(1, duration)) * 100 + '%',
            width: Math.max(0.6, ((Number(s.t1) - Number(s.t0)) / Math.max(1, duration)) * 100) + '%',
            background: ['rgba(90,140,255,0.20)', 'rgba(90,200,160,0.18)',
              'rgba(230,160,90,0.18)', 'rgba(180,120,255,0.18)'][i % 4],
            borderRight: '1px solid rgba(127,127,127,0.25)',
          },
        })),
        frames.map((f, i) => h('div', {
          key: 'fr-' + i, title: fmt(f.t),
          onClick: (ev) => { ev.stopPropagation(); jumpTo(f.t) },
          style: {
            position: 'absolute', top: 4, bottom: 4, width: 2, marginLeft: -1,
            left: (Number(f.t) / Math.max(1, duration)) * 100 + '%',
            background: 'rgba(127,127,127,0.45)',
          },
        })),
        h('div', {
          style: {
            position: 'absolute', top: 0, bottom: 0, width: 2, marginLeft: -1, zIndex: 3,
            left: (duration ? (cursor / duration) : 0) * 100 + '%', background: '#ff5f6d',
          },
        }),
        h('div', { style: { position: 'absolute', top: 2, right: 6, fontSize: 11, opacity: 0.75 } },
          duration ? fmt(duration) : ''),
      )

      const segmentList = h('div', { style: { display: 'flex', flexDirection: 'column', gap: 6 } },
        ((read && read.segments) || []).map((s, i) => h('div', {
          key: 'seg-' + i,
          style: { display: 'flex', gap: 8, padding: '3px 0', borderBottom: '1px solid rgba(127,127,127,0.12)' },
        },
          h('span', { style: { flex: '0 0 44px', opacity: 0.75, fontVariantNumeric: 'tabular-nums' } }, fmt(s.t0)),
          h('span', null, s.text),
        )),
      )

      const frameGrid = h('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 } },
        ((read && read.frames) || []).map((f, i) => h('figure', { key: 'img-' + i, style: { margin: 0 } },
          f.url ? h('img', {
            src: f.url, alt: fmt(f.t),
            style: { width: '100%', borderRadius: 6, display: 'block', background: 'rgba(127,127,127,0.12)' },
          }) : null,
          h('figcaption', { style: Object.assign({}, muted, { fontSize: 11 }) }, fmt(f.t)),
        )),
      )

      const hitsList = hits.length ? h('div', { style: { display: 'flex', flexDirection: 'column', gap: 4 } },
        hits.map((hit, i) => {
          const t = Number((hit.anchor && hit.anchor.t0) || hit.t0 || 0)
          return h('button', {
            key: 'hit-' + i,
            onClick: () => jumpTo(t),
            style: {
              textAlign: 'left', border: '1px solid rgba(127,127,127,0.25)', borderRadius: 6,
              background: 'transparent', color: 'inherit', padding: '4px 6px', cursor: 'pointer', fontSize: 12,
            },
          },
            h('div', { style: { fontWeight: 600 } },
              fmt(t) + (hit.anchor && hit.anchor.text ? ' · ' + hit.anchor.text : '')),
            h('div', { style: Object.assign({}, muted, { maxHeight: 36, overflow: 'hidden' }) },
              String(hit.text || '').slice(0, 160) + '…'))
        }),
      ) : null

      return h('div', { style: shell },
        h('div', { style: row },
          h(VideoPicker, {
            items: (list && list.items) || [],
            value: vid,
            onChange: (next) => { setVid(next); vidRef.current = next },
            onDelete: deleteVideo,
            onClear: clearAll,
          }),
          h('button', { style: btn, title: '刷新视频列表', onClick: loadList, disabled: busy }, '↻'),
        ),
        !vid ? h('div', { style: Object.assign({}, muted, { fontSize: 11 }) },
          '点下拉选择视频；不需要的缓存可在下拉里点 × 删除，或「清空全部缓存」。',
        ) : null,
        detail ? h('div', { style: { display: 'flex', flexDirection: 'column', gap: 2 } },
          h('div', {
            style: { fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
          }, detail.title || detail.video_id),
          h('div', { style: Object.assign({}, muted, { fontSize: 11 }) },
            fmt(duration) + ' · ' + ((detail.index && detail.index.transcript_segments) || 0) + ' 段 · ' +
            ((detail.index && detail.index.shots) || 0) + ' 镜头 · ' +
            ((detail.index && detail.index.danmaku) || 0) + ' 弹幕 · ' +
            (detail.section_source === 'platform' ? '平台章节' : '自动分段')),
        ) : null,
        bar,
        h('div', { style: Object.assign({}, row, { justifyContent: 'space-between' }) },
          h('span', { style: Object.assign({}, muted, { fontSize: 11 }) },
            '当前 ' + fmt(cursor) + (read && read.range && read.range.label ? '（窗口 ' + read.range.label + '）' : '')),
          h('div', { style: { display: 'flex', gap: 6, alignItems: 'center' } },
            h('label', {
              style: { display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, opacity: 0.85, cursor: 'pointer' },
              title: '开启后，点击时间轴会把「看这段」发给 agent',
            },
              h('input', {
                type: 'checkbox', checked: askOnClick,
                onChange: (ev) => setAskOnClick(ev.target.checked),
              }),
              '点击即提问',
            ),
            askNote ? h('span', { style: Object.assign({}, muted, { fontSize: 11 }) }, askNote) : null,
            copied ? h('span', { style: Object.assign({}, muted, { fontSize: 11 }) }, copied) : null,
            h('button', {
              style: btn, disabled: !vid || !duration,
              title: '把当前时间点前后 15s 作为问题发给 agent',
              onClick: () => askAgent(Math.max(0, cursor - 15), Math.min(duration || cursor + 15, cursor + 15)),
            }, '问 agent'),
            h('button', { style: btn, onClick: copyRef, disabled: !read }, '复制引用'),
          ),
        ),
        h('div', { style: row },
          h('input', {
            style: select, value: query, placeholder: '在字幕里搜索（如 磁铁 / crossroads）',
            onChange: (ev) => setQuery(ev.target.value),
            onKeyDown: (ev) => { if (ev.key === 'Enter') doSearch() },
          }),
          h('button', { style: btn, onClick: doSearch, disabled: busy || !query.trim() }, '搜索'),
        ),
        error ? h('div', { style: { color: 'var(--dsw-alias-state-error-primary, #ff6b6b)', fontSize: 11 } }, error) : null,
        busy ? h('div', { style: Object.assign({}, muted, { fontSize: 11 }) }, '加载中…') : null,
        h('div', { style: scroll },
          hitsList,
          hits.length ? h('div', { style: Object.assign({}, muted, { fontSize: 11 }) },
            '点击任一条跳到词级时间锚点') : null,
          h('div', { style: Object.assign({}, muted, { fontSize: 11 }) },
            '点击时间轴跳转；红色竖线为当前位置'),
          segmentList,
          frameGrid,
        ),
      )
    }

    function Title() {
      return h('span', null, '视频时间轴')
    }

    const inject = ['slots', 'sidebarRight', 'sidebarRightTabs']

    function apply(ctx) {
      appCtx = ctx
      ctx.effect(() => ctx.sidebarRightTabs.register({
        id: PANEL_ID,
        kind: KIND,
        title: () => '视频时间轴',
        multiple: false,
        guide: [{
          id: 'timeline',
          order: 30,
          title: () => '视频时间轴',
          description: () => '字幕时间轴 + 关键帧 + 检索定位',
        }],
      }), 'dsh-video-panel: tab type')

      ctx.effect(() => ctx.slots.inject('sidebar.right.pane.tab', () => ctx.slots.register({
        name: 'sidebar.right.pane.tab',
        key: PANEL_ID,
      }, Panel)), 'dsh-video-panel: tab body')

      ctx.effect(() => ctx.slots.inject('sidebar.right.pane.tab.title', () => ctx.slots.register({
        name: 'sidebar.right.pane.tab.title',
        key: PANEL_ID,
      }, Title)), 'dsh-video-panel: tab title')
    }

    exports.inject = inject
    exports.apply = apply
    return module.exports
  },
})
