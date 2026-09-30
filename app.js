(function () {
  var STAGE_W = 1920;
  var IDLE_MS = 2800;

  var body = document.body;
  var stage = document.getElementById("stage");
  var viewport = document.getElementById("viewport");
  var hud = document.getElementById("hud");
  var progress = document.getElementById("progress");
  var dotsBox = document.getElementById("dots");
  var toast = document.getElementById("toast");
  var curEl = document.getElementById("cur");
  var totalEl = document.getElementById("total");
  var modeBtn = document.getElementById("modeBtn");
  var slides = Array.prototype.slice.call(document.querySelectorAll(".slide"));

  var heights = slides.map(function () {
    return 1080;
  });
  var index = 0;
  var dots = [];
  var mode = body.getAttribute("data-mode") === "deck" ? "deck" : "page";
  var fit = stage.getAttribute("data-fit") === "uniform" ? "uniform" : "slide";
  var observer = null;
  var idleTimer = null;
  var toastTimer = null;
  var scrollQueued = false;

  function clamp(value, min, max) {
    return value < min ? min : value > max ? max : value;
  }

  function setVar(name, value) {
    document.documentElement.style.setProperty(name, value);
  }

  function measure(slide) {
    slide.classList.add("is-measuring");
    var height = slide.offsetHeight;
    slide.classList.remove("is-measuring");
    return height;
  }

  function shotHeight(slide) {
    var img = slide.querySelector("img.shot");
    if (!img) return 0;
    if (img.naturalWidth && img.naturalHeight) {
      return Math.round((STAGE_W * img.naturalHeight) / img.naturalWidth);
    }
    var w = parseFloat(img.getAttribute("width"));
    var h = parseFloat(img.getAttribute("height"));
    if (w && h) return Math.round((STAGE_W * h) / w);
    return 0;
  }

  function resolveHeights() {
    slides.forEach(function (slide, i) {
      var declared = parseFloat(slide.getAttribute("data-h"));
      var height = shotHeight(slide) || declared || measure(slide) || 1080;
      heights[i] = Math.round(height);
      slide.style.height = heights[i] + "px";
    });
  }

  function viewportSize() {
    var size = { w: window.innerWidth, h: window.innerHeight };
    if (window.visualViewport) {
      size.w = window.visualViewport.width;
      size.h = window.visualViewport.height;
    }
    return size;
  }

  function layout() {
    var size = viewportSize();
    if (mode === "page") {
      setVar("--zoom", String(Math.min(size.w / STAGE_W, 1)));
      onScroll();
      return;
    }
    var shown = fit === "uniform" ? Math.max.apply(null, heights) : heights[index] || 1080;
    setVar("--stage-h", shown + "px");
    setVar("--scale", String(Math.min(size.w / STAGE_W, size.h / shown)));
  }

  function onScroll() {
    var scrolled = window.scrollY || window.pageYOffset || 0;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    var ratio = max > 4 ? clamp(scrolled / max, 0, 1) : 0;
    if (progress) progress.style.transform = "scaleX(" + ratio + ")";
  }

  function requestScrollSync() {
    if (scrollQueued) return;
    scrollQueued = true;
    requestAnimationFrame(function () {
      scrollQueued = false;
      onScroll();
    });
  }

  function showToast(text, ms) {
    if (!toast) return;
    if (text) toast.textContent = text;
    toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toast.classList.remove("is-visible");
    }, ms || 3200);
  }

  function hint() {
    return mode === "page"
      ? "向下滚动浏览 · 右侧圆点跳转分页 · M 切到逐页预览 · F 全屏"
      : "← → 翻页 · 数字键跳页 · M 回到连续滚动 · F 全屏 · P 导出 PDF";
  }

  function ping() {
    body.classList.remove("is-idle");
    clearTimeout(idleTimer);
    idleTimer = setTimeout(function () {
      body.classList.add("is-idle");
    }, IDLE_MS);
  }

  function syncDots(active) {
    dots.forEach(function (dot, i) {
      dot.classList.toggle("is-active", i === active);
    });
  }

  function render() {
    slides.forEach(function (slide, i) {
      slide.classList.toggle("is-active", i === index);
    });
    syncDots(index);
    if (curEl) curEl.textContent = String(index + 1);
    var prev = hud && hud.querySelector('[data-act="prev"]');
    var next = hud && hud.querySelector('[data-act="next"]');
    if (prev) prev.disabled = index === 0;
    if (next) next.disabled = index === slides.length - 1;
    layout();
    if (mode !== "deck") return;
    var hash = "#" + (index + 1);
    if (window.location.hash === hash) return;
    try {
      history.replaceState(null, "", hash);
    } catch (error) {
      window.location.hash = hash;
    }
  }

  function go(target) {
    var next = clamp(target, 0, slides.length - 1);
    if (next === index) return;
    index = next;
    render();
    ping();
  }

  function jumpTo(i) {
    if (mode === "page") {
      slides[i].scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    go(i);
  }

  function observeSections() {
    if (mode !== "page" || !window.IntersectionObserver) return;
    observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          index = slides.indexOf(entry.target);
          syncDots(index);
        });
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: 0 }
    );
    slides.forEach(function (slide) {
      observer.observe(slide);
    });
  }

  function disconnectSections() {
    if (!observer) return;
    observer.disconnect();
    observer = null;
  }

  function buildDots() {
    if (!dotsBox || slides.length < 2) return;
    slides.forEach(function (_, i) {
      var dot = document.createElement("button");
      dot.className = "dot";
      dot.setAttribute("aria-label", "跳到第 " + (i + 1) + " 段");
      dot.addEventListener("click", function () {
        jumpTo(i);
      });
      dotsBox.appendChild(dot);
      dots.push(dot);
    });
  }

  function setMode(next) {
    mode = next;
    body.setAttribute("data-mode", mode);
    if (modeBtn) modeBtn.textContent = mode === "page" ? "逐页预览" : "连续滚动";
    disconnectSections();
    if (mode === "deck") {
      index = 0;
      try {
        window.scrollTo({ top: 0, behavior: "instant" });
      } catch (error) {
        window.scrollTo(0, 0);
      }
      render();
    } else {
      try {
        window.scrollTo({ top: 0, behavior: "instant" });
      } catch (error) {
        window.scrollTo(0, 0);
      }
      layout();
      observeSections();
    }
    onScroll();
    showToast(hint(), 3600);
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
  }

  function handleAction(act) {
    if (act === "prev") go(index - 1);
    else if (act === "next") go(index + 1);
    else if (act === "mode") setMode(mode === "page" ? "deck" : "page");
    else if (act === "fullscreen") toggleFullscreen();
    else if (act === "print") window.print();
  }

  function wireShots() {
    Array.prototype.forEach.call(document.querySelectorAll("img.shot"), function (img) {
      var slide = img.closest(".slide");
      if (!slide) return;
      function loaded() {
        slide.classList.add("uses-shot");
        img.style.display = "";
        resolveHeights();
        layout();
      }
      function failed() {
        slide.classList.remove("uses-shot");
        img.style.display = "none";
      }
      img.addEventListener("load", loaded);
      img.addEventListener("error", failed);
      if (!img.complete) return;
      if (img.naturalWidth > 0) loaded();
      else failed();
    });
  }

  document.addEventListener("keydown", function (event) {
    var key = event.key;
    var acts = {
      ArrowRight: "next",
      ArrowDown: "next",
      PageDown: "next",
      " ": "next",
      ArrowLeft: "prev",
      ArrowUp: "prev",
      PageUp: "prev"
    };
    if (acts[key]) {
      if (mode === "page") return;
      event.preventDefault();
      handleAction(acts[key]);
      return;
    }
    if (key === "Home") return go(0);
    if (key === "End") return go(slides.length - 1);
    if (key === "f" || key === "F") return toggleFullscreen();
    if (key === "p" || key === "P") return window.print();
    if (key === "m" || key === "M") return setMode(mode === "page" ? "deck" : "page");
    if (key >= "1" && key <= "9") return jumpTo(Number(key) - 1);
    if (key === "?" || key === "/") return showToast(hint());
  });

  if (hud) {
    hud.addEventListener("click", function (event) {
      var button = event.target.closest("[data-act]");
      if (button) handleAction(button.getAttribute("data-act"));
    });
  }

  viewport.addEventListener("click", function (event) {
    if (mode === "page") return;
    if (event.target.closest("a, button, input, textarea, select")) return;
    if (slides.length < 2) return;
    var ratio = event.clientX / window.innerWidth;
    if (ratio < 0.22) go(index - 1);
    else if (ratio > 0.78) go(index + 1);
  });

  var touchStartX = 0;
  viewport.addEventListener(
    "touchstart",
    function (event) {
      touchStartX = event.changedTouches[0].clientX;
    },
    { passive: true }
  );
  viewport.addEventListener(
    "touchend",
    function (event) {
      if (mode === "page") return;
      var delta = event.changedTouches[0].clientX - touchStartX;
      if (Math.abs(delta) > 56) go(index + (delta < 0 ? 1 : -1));
    },
    { passive: true }
  );

  window.addEventListener("resize", layout);
  window.addEventListener("orientationchange", layout);
  window.addEventListener("scroll", requestScrollSync, { passive: true });
  window.addEventListener("scroll", ping, { passive: true });
  window.addEventListener("hashchange", function () {
    if (mode !== "deck") return;
    var parsed = Number(window.location.hash.replace("#", ""));
    if (parsed >= 1 && parsed <= slides.length) go(parsed - 1);
  });
  document.addEventListener("mousemove", ping);
  document.addEventListener("keydown", ping);

  if (slides.length < 2) body.classList.add("is-single");
  if (totalEl) totalEl.textContent = String(slides.length);
  if (modeBtn) modeBtn.textContent = mode === "page" ? "逐页预览" : "连续滚动";
  slides.forEach(function (slide, i) {
    if (!slide.id) slide.id = "p" + (i + 1);
  });

  buildDots();
  wireShots();
  resolveHeights();
  var initial = Number(window.location.hash.replace("#", ""));
  index = mode === "deck" && initial >= 1 && initial <= slides.length ? initial - 1 : 0;
  render();
  observeSections();
  onScroll();
  ping();
  showToast(hint(), 4200);

  window.addEventListener("load", function () {
    resolveHeights();
    layout();
    onScroll();
  });

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      resolveHeights();
      layout();
    });
  }
})();
