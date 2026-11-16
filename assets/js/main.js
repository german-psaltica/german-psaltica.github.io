/* German Psaltica — theme, catalog filtering and small conveniences. */
(function () {
  "use strict";

  var root = document.documentElement;

  /* ---------------------------------------------------------------------
     Theme
     --------------------------------------------------------------------- */

  var themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try {
        localStorage.setItem("psaltica-theme", next);
      } catch (error) {}
    });
  }

  /* ---------------------------------------------------------------------
     Mobile menu
     --------------------------------------------------------------------- */

  var siteMenu = document.querySelector(".site-menu");
  if (siteMenu) {
    siteMenu.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        siteMenu.open = false;
      });
    });

    document.addEventListener("click", function (event) {
      if (siteMenu.open && !siteMenu.contains(event.target)) {
        siteMenu.open = false;
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && siteMenu.open) {
        siteMenu.open = false;
        var toggle = siteMenu.querySelector("summary");
        if (toggle) {
          toggle.focus();
        }
      }
    });
  }

  /* ---------------------------------------------------------------------
     Copy page link
     --------------------------------------------------------------------- */

  document.querySelectorAll("[data-copy-link]").forEach(function (button) {
    button.addEventListener("click", function () {
      var original = button.innerHTML;
      var markCopied = function () {
        button.classList.add("is-copied");
        button.textContent = "Link kopiert";
        window.setTimeout(function () {
          button.classList.remove("is-copied");
          button.innerHTML = original;
        }, 1800);
      };

      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(window.location.href).then(markCopied, function () {
          window.prompt("Link kopieren:", window.location.href);
        });
      } else {
        window.prompt("Link kopieren:", window.location.href);
      }
    });
  });

  /* ---------------------------------------------------------------------
     Library catalog
     --------------------------------------------------------------------- */

  var grid = document.getElementById("library-grid");
  if (!grid) {
    return;
  }

  var cards = Array.prototype.slice.call(grid.querySelectorAll(".doc-card"));
  var searchInput = document.getElementById("library-search");
  var categorySelect = document.getElementById("filter-category");
  var modeSelect = document.getElementById("filter-mode");
  var sortSelect = document.getElementById("filter-sort");
  var archiveInput = document.getElementById("filter-archive");
  var resetButton = document.getElementById("library-reset");
  var emptyResetButton = document.getElementById("library-empty-reset");
  var countOutput = document.getElementById("library-count");
  var emptyState = document.getElementById("library-empty");
  var summary = document.getElementById("library-filter-summary");
  if (!searchInput || !categorySelect || !modeSelect || !sortSelect || !archiveInput) {
    return;
  }

  function normalize(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/ß/g, "ss")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function selectedLabel(select) {
    if (!select.value) {
      return "";
    }
    var option = select.options[select.selectedIndex];
    return option ? option.textContent.trim() : "";
  }

  var params = new URLSearchParams(window.location.search);
  var state = {
    q: params.get("q") || "",
    category: params.get("category") || "",
    mode: params.get("mode") || "",
    sort: params.get("sort") || "title",
    archive: params.get("archive") === "1",
    section: params.get("section") || "",
    sectionName: params.get("sectionName") || ""
  };

  searchInput.value = state.q;
  if (Array.prototype.some.call(categorySelect.options, function (option) { return option.value === state.category; })) {
    categorySelect.value = state.category;
  }
  if (Array.prototype.some.call(modeSelect.options, function (option) { return option.value === state.mode; })) {
    modeSelect.value = state.mode;
  }
  if (Array.prototype.some.call(sortSelect.options, function (option) { return option.value === state.sort; })) {
    sortSelect.value = state.sort;
  }
  archiveInput.checked = state.archive;

  function currentQuery() {
    return normalize(searchInput.value);
  }

  function apply(updateUrl) {
    var query = currentQuery();
    var tokens = query ? query.split(/\s+/).filter(Boolean) : [];
    var category = categorySelect.value;
    var mode = modeSelect.value;
    var archive = archiveInput.checked;
    var sort = sortSelect.value;
    var archiveContext = category === "99_Archiv" || state.section.indexOf("99_Archiv") === 0;
    var sectionPrefix = state.section ? state.section + "/" : "";
    var visibleCount = 0;

    cards.forEach(function (card) {
      var cardSearch = card.dataset.search || "";
      var cardCategory = card.dataset.category || "";
      var cardMode = card.dataset.mode || "";
      var cardSection = card.dataset.section || "";
      var isArchive = card.dataset.archive === "true";

      var searchOk = tokens.every(function (token) {
        return cardSearch.indexOf(token) !== -1;
      });
      var categoryOk = !category || cardCategory === category;
      var modeOk = !mode || (mode === "none" ? cardMode === "" : cardMode === mode);
      var sectionOk = !state.section || cardSection === state.section || cardSection.indexOf(sectionPrefix) === 0;
      var archiveOk = archive || !isArchive || archiveContext;
      var visible = searchOk && categoryOk && modeOk && sectionOk && archiveOk;

      card.hidden = !visible;
      if (visible) {
        visibleCount += 1;
      }
    });

    if (countOutput) {
      countOutput.textContent = visibleCount === cards.length
        ? cards.length + (cards.length === 1 ? " Note" : " Noten")
        : visibleCount + " von " + cards.length + " Noten";
    }

    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }

    var activeParts = [];
    if (searchInput.value.trim()) {
      activeParts.push("Suche: „" + searchInput.value.trim() + "“");
    }
    var categoryLabel = selectedLabel(categorySelect);
    if (categoryLabel && !state.sectionName) {
      activeParts.push("Bereich: " + categoryLabel);
    }
    var modeLabel = selectedLabel(modeSelect);
    if (modeLabel) {
      activeParts.push("Modus: " + modeLabel);
    }
    if (state.sectionName) {
      activeParts.push("Bereich: " + state.sectionName);
    }
    if (archive) {
      activeParts.push("Archiv einbezogen");
    }
    if (summary) {
      summary.hidden = activeParts.length === 0;
      summary.textContent = activeParts.join(" · ");
    }
    if (resetButton) {
      resetButton.hidden = activeParts.length === 0;
    }

    var comparator = function (a, b) {
      var titleA = (a.dataset.title || "").toLocaleLowerCase("de");
      var titleB = (b.dataset.title || "").toLocaleLowerCase("de");
      var byTitle = titleA.localeCompare(titleB, "de", { numeric: true, sensitivity: "base" });
      if (sort === "newest" || sort === "oldest") {
        var createdA = a.dataset.created || "";
        var createdB = b.dataset.created || "";
        if (createdA !== createdB) {
          return sort === "newest" ? createdB.localeCompare(createdA) : createdA.localeCompare(createdB);
        }
        return byTitle;
      }
      if (sort === "pages") {
        var pagesA = parseInt(a.dataset.pages || "0", 10);
        var pagesB = parseInt(b.dataset.pages || "0", 10);
        if (pagesA !== pagesB) {
          return pagesB - pagesA;
        }
        return byTitle;
      }
      if (sort === "size") {
        var sizeA = parseInt(a.dataset.size || "0", 10);
        var sizeB = parseInt(b.dataset.size || "0", 10);
        if (sizeA !== sizeB) {
          return sizeB - sizeA;
        }
        return byTitle;
      }
      return byTitle;
    };

    cards.slice().sort(comparator).forEach(function (card) {
      grid.appendChild(card);
    });

    if (updateUrl) {
      var next = new URLSearchParams();
      if (searchInput.value.trim()) {
        next.set("q", searchInput.value.trim());
      }
      if (category) {
        next.set("category", category);
      }
      if (mode) {
        next.set("mode", mode);
      }
      if (sort !== "title") {
        next.set("sort", sort);
      }
      if (archive) {
        next.set("archive", "1");
      }
      if (state.section) {
        next.set("section", state.section);
      }
      if (state.sectionName) {
        next.set("sectionName", state.sectionName);
      }
      var queryString = next.toString();
      var nextUrl = window.location.pathname + (queryString ? "?" + queryString : "") + window.location.hash;
      window.history.replaceState(null, "", nextUrl);
    }
  }

  var searchTimer;
  searchInput.addEventListener("input", function () {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(function () {
      apply(true);
    }, 120);
  });

  categorySelect.addEventListener("change", function () {
    if (!categorySelect.value || (state.section && state.section.indexOf(categorySelect.value) !== 0)) {
      state.section = "";
      state.sectionName = "";
    }
    apply(true);
  });

  modeSelect.addEventListener("change", function () {
    apply(true);
  });

  sortSelect.addEventListener("change", function () {
    apply(true);
  });

  archiveInput.addEventListener("change", function () {
    apply(true);
  });

  function resetFilters() {
    searchInput.value = "";
    categorySelect.value = "";
    modeSelect.value = "";
    sortSelect.value = "title";
    archiveInput.checked = false;
    state.section = "";
    state.sectionName = "";
    apply(true);
    searchInput.focus();
  }

  if (resetButton) {
    resetButton.addEventListener("click", resetFilters);
  }
  if (emptyResetButton) {
    emptyResetButton.addEventListener("click", resetFilters);
  }

  document.addEventListener("keydown", function (event) {
    var target = event.target;
    var tag = target && target.tagName ? target.tagName.toLowerCase() : "";
    var typing = tag === "input" || tag === "textarea" || tag === "select" || (target && target.isContentEditable);

    if (event.key === "/" && !typing) {
      event.preventDefault();
      searchInput.focus();
    }

    if (event.key === "Escape" && document.activeElement === searchInput) {
      searchInput.value = "";
      apply(true);
    }
  });

  window.addEventListener("popstate", function () {
    var nextParams = new URLSearchParams(window.location.search);
    state.q = nextParams.get("q") || "";
    state.category = nextParams.get("category") || "";
    state.mode = nextParams.get("mode") || "";
    state.sort = nextParams.get("sort") || "title";
    state.archive = nextParams.get("archive") === "1";
    state.section = nextParams.get("section") || "";
    state.sectionName = nextParams.get("sectionName") || "";
    searchInput.value = state.q;
    categorySelect.value = state.category;
    modeSelect.value = state.mode;
    sortSelect.value = state.sort;
    archiveInput.checked = state.archive;
    apply(false);
  });

  apply(false);
})();
