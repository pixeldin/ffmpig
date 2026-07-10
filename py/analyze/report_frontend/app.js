(function () {
  "use strict";

  const state = {
    payload: null,
    allFiles: [],
  };

  const els = {
    updatedAt: document.getElementById("updatedAt"),
    resultCount: document.getElementById("resultCount"),
    searchInput: document.getElementById("searchInput"),
    clearSearch: document.getElementById("clearSearch"),
    viewSelect: document.getElementById("viewSelect"),
    visitFilter: document.getElementById("visitFilter"),
    sortSelect: document.getElementById("sortSelect"),
    timeFilter: document.getElementById("timeFilter"),
    customRange: document.getElementById("customRange"),
    dateFrom: document.getElementById("dateFrom"),
    dateTo: document.getElementById("dateTo"),
    applyRange: document.getElementById("applyRange"),
    themeToggle: document.getElementById("themeToggle"),
    treeView: document.getElementById("treeView"),
    listView: document.getElementById("listView"),
    error: document.getElementById("error"),
    imageModal: document.getElementById("imageModal"),
    modalImage: document.getElementById("modalImage"),
    videoModal: document.getElementById("videoModal"),
    videoPlayer: document.getElementById("videoPlayer"),
  };

  function flattenData(data, path) {
    let files = [];
    Object.entries(data || {}).forEach(([key, value]) => {
      if (key === "files" && Array.isArray(value)) {
        value.forEach((file) => {
          const times = Array.isArray(file.times) ? file.times : [];
          files.push({
            ...file,
            path,
            times,
            count: Number(file.count || 0),
            modifiedTs: file.modifiedTs ?? null,
            modifiedTime: file.modifiedTime ?? null,
            lastTime: times.length ? times[times.length - 1] : "",
          });
        });
        return;
      }
      if (value && typeof value === "object") {
        const nextPath = path ? `${path}/${key}` : key;
        files = files.concat(flattenData(value, nextPath));
      }
    });
    return files;
  }

  function parseDate(value) {
    if (!value) return null;
    const parsed = new Date(value.replace(" ", "T"));
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function getTimePredicate() {
    const value = els.timeFilter.value;
    if (value === "all") return () => true;

    const now = new Date();
    let from = null;
    let to = null;
    if (value === "1w") from = new Date(now.getTime() - 7 * 86400000);
    if (value === "1m") from = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
    if (value === "3m") from = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
    if (value === "custom") {
      from = els.dateFrom.value ? new Date(`${els.dateFrom.value}T00:00:00`) : null;
      to = els.dateTo.value ? new Date(`${els.dateTo.value}T23:59:59`) : null;
    }

    return (file) => {
      if (!file.times.length) return false;
      return file.times.some((time) => {
        const date = parseDate(time);
        if (!date) return false;
        if (from && date < from) return false;
        if (to && date > to) return false;
        return true;
      });
    };
  }

  function getFilteredFiles() {
    const keyword = els.searchInput.value.trim().toLowerCase();
    const visitFilter = els.visitFilter.value;
    const timePredicate = getTimePredicate();
    let files = state.allFiles.filter((file) => {
      const haystack = `${file.path}/${file.name}`.toLowerCase();
      if (keyword && !haystack.includes(keyword)) return false;
      if (visitFilter === "visited" && file.count <= 0) return false;
      if (visitFilter === "unvisited" && file.count > 0) return false;
      return timePredicate(file);
    });

    const sort = els.sortSelect.value;
    if (sort === "count-desc") files = files.sort((a, b) => b.count - a.count);
    if (sort === "count-asc") files = files.sort((a, b) => a.count - b.count);
    if (sort === "time-desc") files = files.sort((a, b) => String(b.lastTime).localeCompare(String(a.lastTime)));
    if (sort === "time-asc") files = files.sort((a, b) => String(a.lastTime).localeCompare(String(b.lastTime)));
    if (sort === "modified-desc") files = files.sort((a, b) => nullLastCompare(b.modifiedTs, a.modifiedTs));
    if (sort === "modified-asc") files = files.sort((a, b) => nullLastCompare(a.modifiedTs, b.modifiedTs));
    return files;
  }

  function nullLastCompare(a, b) {
    const aMissing = a === null || a === undefined || a === "";
    const bMissing = b === null || b === undefined || b === "";
    if (aMissing && bMissing) return 0;
    if (aMissing) return 1;
    if (bMissing) return -1;
    return Number(a) - Number(b);
  }

  function fileUrl(file) {
    const base = (state.payload.chfsBaseUrl || "").replace(/\/$/, "");
    const encoded = `${file.path}/${file.name}`.split("/").map(encodeURIComponent).join("/");
    return `${base}/chfs/shared/FILES/${encoded}`;
  }

  function withQueryParams(url, params) {
    const [base, hash = ""] = url.split("#");
    const [path, query = ""] = base.split("?");
    const searchParams = new URLSearchParams(query);
    Object.entries(params).forEach(([key, value]) => {
      searchParams.set(key, value);
    });
    const nextQuery = searchParams.toString();
    return `${path}${nextQuery ? `?${nextQuery}` : ""}${hash ? `#${hash}` : ""}`;
  }

  function previewUrl(file) {
    return withQueryParams(fileUrl(file), { v: "1" });
  }

  function verifiedMediaUrl(file) {
    return withQueryParams(fileUrl(file), { v: "1", vvv: "1" });
  }

  function isVideo(file) {
    return /\.(mp4|m4v|webm|mov|mp3|m4a|aac|wav|flac|ogg)$/i.test(file.name);
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }

  function showCopyState(button, text) {
    const original = button.textContent;
    button.textContent = text;
    button.disabled = true;
    window.setTimeout(() => {
      button.textContent = original;
      button.disabled = false;
    }, 1200);
  }

  function renderFile(file, includePath) {
    const row = document.createElement("li");
    row.className = `file-row${file.count > 0 ? "" : " unvisited"}`;
    const filePreviewUrl = previewUrl(file);
    const mediaUrl = verifiedMediaUrl(file);

    const main = document.createElement("div");
    main.className = "file-main";
    const link = document.createElement("a");
    link.className = "file-name";
    link.href = filePreviewUrl;
    link.textContent = file.name;
    if (isVideo(file)) {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        showVideo(filePreviewUrl);
      });
    }
    main.appendChild(link);

    const meta = document.createElement("div");
    meta.className = "file-meta";
    meta.textContent = [
      file.exists === false ? "文件缺失" : "",
      formatSize(file.size),
      file.modifiedTime ? `更新 ${file.modifiedTime}` : "",
    ].filter(Boolean).join(" / ");
    main.appendChild(meta);

    if (includePath) {
      const path = document.createElement("div");
      path.className = "file-path";
      path.textContent = file.path;
      main.appendChild(path);
    }

    const count = document.createElement("span");
    count.className = "count-badge";
    count.textContent = `${file.count} 次`;

    const times = document.createElement("div");
    times.className = "file-times";
    times.textContent = file.times.length ? file.times.join(" / ") : "暂无访问";

    row.appendChild(main);
    row.appendChild(count);
    row.appendChild(times);

    const actions = document.createElement("div");
    actions.className = "file-actions";

    if (file.preview) {
      const img = document.createElement("img");
      img.className = "preview-thumb";
      img.src = file.preview;
      img.alt = `${file.name} 预览`;
      img.loading = "lazy";
      img.addEventListener("click", () => showImage(file.preview));
      actions.appendChild(img);
    }

    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "copy-link-button";
    copyButton.textContent = "复制链接";
    copyButton.title = filePreviewUrl;
    copyButton.addEventListener("click", async () => {
      try {
        await copyText(filePreviewUrl);
        showCopyState(copyButton, "已复制");
      } catch (error) {
        showCopyState(copyButton, "复制失败");
      }
    });
    actions.appendChild(copyButton);

    if (isVideo(file)) {
      const targetButton = document.createElement("button");
      targetButton.type = "button";
      targetButton.className = "target-link-button";
      targetButton.textContent = "选中目标";
      targetButton.title = mediaUrl;
      targetButton.addEventListener("click", () => {
        if (window.confirm(`确认选中该目标并记录访问标识？\n${file.name}`)) {
          showVideo(mediaUrl);
        }
      });
      actions.appendChild(targetButton);
    }

    row.appendChild(actions);
    return row;
  }

  function buildTree(files) {
    const root = {};
    files.forEach((file) => {
      const parts = file.path ? file.path.split("/") : [];
      let current = root;
      parts.forEach((part) => {
        current[part] = current[part] || {};
        current = current[part];
      });
      current.files = current.files || [];
      current.files.push(file);
    });
    return root;
  }

  function renderTreeNode(name, node) {
    const li = document.createElement("li");
    li.className = "tree-node";
    const title = document.createElement("button");
    title.type = "button";
    title.className = "dir-title";
    title.textContent = name;
    title.addEventListener("click", () => li.classList.toggle("collapsed"));
    li.appendChild(title);

    const list = document.createElement("ul");
    Object.entries(node).forEach(([key, value]) => {
      if (key !== "files") list.appendChild(renderTreeNode(key, value));
    });
    (node.files || []).forEach((file) => list.appendChild(renderFile(file, false)));
    li.appendChild(list);
    return li;
  }

  function renderTree(files) {
    const tree = buildTree(files);
    els.treeView.replaceChildren();
    Object.entries(tree).forEach(([key, value]) => {
      if (key !== "files") els.treeView.appendChild(renderTreeNode(key, value));
    });
    (tree.files || []).forEach((file) => els.treeView.appendChild(renderFile(file, true)));
  }

  function renderList(files) {
    const list = document.createElement("ul");
    list.className = "tree-view";
    files.forEach((file) => list.appendChild(renderFile(file, true)));
    els.listView.replaceChildren(list);
  }

  function refresh() {
    const files = getFilteredFiles();
    els.resultCount.textContent = `${files.length} / ${state.allFiles.length} 个文件`;
    const isTree = els.viewSelect.value === "tree";
    els.treeView.classList.toggle("hidden", !isTree);
    els.listView.classList.toggle("hidden", isTree);
    if (isTree) renderTree(files);
    else renderList(files);
  }

  function formatSize(size) {
    const value = Number(size || 0);
    if (!value) return "";
    if (value < 1024) return `${value} B`;
    if (value < 1048576) return `${(value / 1024).toFixed(1)} KB`;
    if (value < 1073741824) return `${(value / 1048576).toFixed(1)} MB`;
    return `${(value / 1073741824).toFixed(1)} GB`;
  }

  function showImage(src) {
    els.modalImage.src = src;
    els.imageModal.classList.remove("hidden");
  }

  function showVideo(src) {
    els.videoPlayer.src = src;
    els.videoModal.classList.remove("hidden");
    els.videoPlayer.play().catch(() => {});
  }

  function closeModals() {
    els.imageModal.classList.add("hidden");
    els.videoModal.classList.add("hidden");
    els.videoPlayer.pause();
    els.videoPlayer.removeAttribute("src");
  }

  function applyTheme(theme) {
    const nextTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = nextTheme;
    els.themeToggle.setAttribute("aria-pressed", String(nextTheme === "dark"));
    els.themeToggle.setAttribute("aria-label", nextTheme === "dark" ? "切换浅色模式" : "切换深色模式");
    els.themeToggle.querySelector(".theme-toggle-icon").textContent = nextTheme === "dark" ? "☾" : "☀";
    localStorage.setItem("report-theme", nextTheme);
  }

  function initTheme() {
    const savedTheme = localStorage.getItem("report-theme");
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(savedTheme || (prefersDark ? "dark" : "light"));
  }

  async function loadPayload() {
    if (window.__REPORT_DATA__) return window.__REPORT_DATA__;
    const response = await fetch("data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`data.json 加载失败: ${response.status}`);
    return response.json();
  }

  function bindEvents() {
    els.searchInput.addEventListener("input", refresh);
    els.clearSearch.addEventListener("click", () => {
      els.searchInput.value = "";
      refresh();
    });
    els.viewSelect.addEventListener("change", refresh);
    els.visitFilter.addEventListener("change", refresh);
    els.sortSelect.addEventListener("change", refresh);
    els.timeFilter.addEventListener("change", () => {
      els.customRange.classList.toggle("hidden", els.timeFilter.value !== "custom");
      if (els.timeFilter.value !== "custom") refresh();
    });
    els.applyRange.addEventListener("click", refresh);
    els.themeToggle.addEventListener("click", () => {
      const current = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
      applyTheme(current === "dark" ? "light" : "dark");
    });
    document.querySelectorAll(".modal, .modal-close").forEach((el) => {
      el.addEventListener("click", closeModals);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeModals();
    });
    els.modalImage.addEventListener("click", (event) => event.stopPropagation());
    els.videoPlayer.addEventListener("click", (event) => event.stopPropagation());
  }

  async function init() {
    initTheme();
    bindEvents();
    try {
      state.payload = await loadPayload();
      state.allFiles = flattenData(state.payload.logData || {}, "");
      els.updatedAt.textContent = `更新时间: ${state.payload.updatedAt || "未知"}`;
      refresh();
    } catch (error) {
      els.error.textContent = error.message;
      els.error.classList.remove("hidden");
    }
  }

  init();
})();
