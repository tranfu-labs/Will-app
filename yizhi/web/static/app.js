/* yizhi panel client: SSE subscription + approval actions + timeline live rows.
   Deliberately dependency-free (~90 lines): the interaction surface is tiny and a
   vendored framework would be an unauditable blob in an offline-first repo. */
(function () {
  "use strict";

  var page = document.body.dataset.page;
  var dot = document.getElementById("sse-dot");
  var label = document.getElementById("sse-label");

  // --- live state updates -------------------------------------------------
  function setField(name, value) {
    document.querySelectorAll('[data-field="' + name + '"]').forEach(function (el) {
      el.textContent = value;
    });
  }

  function applyState(now) {
    if (!now.has_state) return;
    ["goal_title", "goal_description", "goal_status", "vision",
     "plan_cursor", "plan_total", "plan_revision", "plan_stall_count",
     "intention_title", "intention_rationale", "endorsed_drive",
     "budget_pressure", "loop_count", "last_surprise"].forEach(function (k) {
      if (now[k] !== undefined) setField(k, now[k]);
    });
    setField("budget_balance", Number(now.budget_balance).toFixed(1));
    setField("budget_total_spent", Number(now.budget_total_spent).toFixed(1));
    setField("budget_total_replenished", Number(now.budget_total_replenished).toFixed(1));
    setField("budget_state", now.budget_halted ? "已停机" : "运行中");
    var planBar = document.querySelector('[data-field="plan_pct_bar"]');
    if (planBar) planBar.style.width = now.plan_pct + "%";
    var budgetBar = document.querySelector('[data-field="budget_pct_bar"]');
    if (budgetBar) budgetBar.style.width = now.budget_pct + "%";
    var badge = document.querySelector('[data-field="goal_status"]');
    if (badge) badge.className = "badge st-" + now.goal_status;
  }

  function prependEventRow(ev) {
    var rows = document.getElementById("event-rows");
    if (!rows) return;
    var tr = document.createElement("tr");
    tr.className = "flash";
    [ev.ts.slice(0, 19), ev.type, ev.aggregate_type, ev.summary].forEach(function (text, i) {
      var td = document.createElement("td");
      if (i === 0 || i === 2) td.className = "mono" + (i === 2 ? " muted" : "");
      if (i === 1) {
        var b = document.createElement("span");
        b.className = "badge ev";
        b.textContent = text;
        td.appendChild(b);
      } else {
        td.textContent = text;
      }
      tr.appendChild(td);
    });
    rows.insertBefore(tr, rows.firstChild);
  }

  // --- SSE ------------------------------------------------------------------
  if (window.EventSource) {
    var source = new EventSource("/stream");
    source.addEventListener("open", function () {
      dot.className = "on dot";
      label.textContent = "实时";
    });
    source.addEventListener("error", function () {
      dot.className = "off dot";
      label.textContent = "已断开，重连中…";
    });
    source.addEventListener("state", function (e) {
      try { applyState(JSON.parse(e.data)); } catch (err) { /* keep panel alive */ }
    });
    source.addEventListener("semantic_event", function (e) {
      try {
        var ev = JSON.parse(e.data);
        if (page === "timeline") prependEventRow(ev);
        if (page === "approvals" && ev.type === "ActionProposed") location.reload();
      } catch (err) { /* keep panel alive */ }
    });
  }

  // --- approval actions -----------------------------------------------------
  document.querySelectorAll(".approval .btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var cardEl = btn.closest(".approval");
      var cid = cardEl.dataset.cid;
      var verb = btn.dataset.verb;
      cardEl.querySelectorAll(".btn").forEach(function (b) { b.disabled = true; });
      fetch("/api/approvals/" + encodeURIComponent(cid), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verb: verb }),
      })
        .then(function (resp) { if (!resp.ok) throw new Error("HTTP " + resp.status); return resp.json(); })
        .then(function () {
          cardEl.querySelector(".actions").innerHTML =
            '<span class="badge st-done">已提交（' + verb + '），待 loop 拉取</span>';
        })
        .catch(function (err) {
          cardEl.querySelectorAll(".btn").forEach(function (b) { b.disabled = false; });
          alert("提交失败：" + err.message);
        });
    });
  });
  // --- conversation page ------------------------------------------------------
  var chatLog = document.getElementById("chat-log");
  if (chatLog) {
    var knownCount = parseInt(chatLog.dataset.count || "0", 10);

    function msgNode(m) {
      var wrap = document.createElement("div");
      wrap.className = "msg " + m.role;
      var meta = document.createElement("div");
      meta.className = "msg-meta";
      var badge = document.createElement("span");
      badge.className = "badge lbl-" + m.label;
      badge.textContent = m.label;
      var source = document.createElement("span");
      source.className = "badge source";
      source.textContent = m.source || m.role;
      var ts = document.createElement("span");
      ts.className = "mono muted";
      ts.textContent = (m.ts || "").slice(0, 19);
      meta.appendChild(badge);
      meta.appendChild(source);
      meta.appendChild(ts);
      wrap.appendChild(meta);
      if (m.title) {
        var title = document.createElement("div");
        title.className = "msg-title";
        title.textContent = m.title;
        wrap.appendChild(title);
      }
      var text = document.createElement("div");
      text.className = "msg-text";
      text.textContent = m.text;
      wrap.appendChild(text);
      if (m.pending_action) {
        var pending = document.createElement("div");
        pending.className = "pending-action";
        var info = document.createElement("div");
        info.className = "small-text";
        info.textContent = "待确认：" + m.pending_action.verb + " · " + m.pending_action.risk;
        var btn = document.createElement("button");
        btn.className = "btn approve chat-confirm";
        btn.dataset.actionId = m.pending_action.id;
        btn.textContent = "确认提交";
        pending.appendChild(info);
        pending.appendChild(btn);
        wrap.appendChild(pending);
      }
      return wrap;
    }

    function renderChat(messages) {
      if (messages.length === knownCount) return;
      knownCount = messages.length;
      var empty = document.getElementById("chat-empty");
      if (empty) empty.remove();
      chatLog.replaceChildren.apply(chatLog, messages.map(msgNode));
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    function refreshChat() {
      fetch("/api/chat")
        .then(function (r) { return r.json(); })
        .then(renderChat)
        .catch(function () { /* keep polling */ });
    }

    function sendChat(verb, text) {
      return fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ verb: verb, text: text }),
      }).then(function (resp) {
        if (!resp.ok) return resp.json().then(function (e) { throw new Error(e.detail || resp.status); });
        return resp.json();
      });
    }

    function confirmAction(actionId) {
      return fetch("/api/chat/confirm/" + encodeURIComponent(actionId), { method: "POST" })
        .then(function (resp) {
          if (!resp.ok) return resp.json().then(function (e) { throw new Error(e.detail || resp.status); });
          return resp.json();
        });
    }

    var textarea = document.getElementById("chat-text");
    var sendBtn = document.getElementById("chat-send");

    function submitMessage() {
      var text = textarea.value.trim();
      if (!text) return;
      sendBtn.disabled = true;
      sendChat("auto", text)
        .then(function () { textarea.value = ""; refreshChat(); })
        .catch(function (err) { alert("发送失败：" + err.message); })
        .finally(function () { sendBtn.disabled = false; textarea.focus(); });
    }

    sendBtn.addEventListener("click", submitMessage);
    textarea.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitMessage(); }
    });

    document.getElementById("chat-kill-goal").addEventListener("click", function () {
      sendChat("kill", "goal")
        .then(refreshChat)
        .catch(function (err) { alert("发送失败：" + err.message); });
    });

    chatLog.addEventListener("click", function (e) {
      if (!e.target.classList.contains("chat-confirm")) return;
      var id = e.target.dataset.actionId;
      e.target.disabled = true;
      confirmAction(id)
        .then(refreshChat)
        .catch(function (err) {
          e.target.disabled = false;
          alert("确认失败：" + err.message);
        });
    });

    chatLog.scrollTop = chatLog.scrollHeight;
    setInterval(refreshChat, 3000);
  }
})();
