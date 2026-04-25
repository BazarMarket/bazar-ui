(function () {
    var STORAGE_KEY = 'bazar-re-open-v2';
    var TARGET_PREFIXES = ['For Sale', 'For Long-term Rent', 'For Short-term Rent'];

    function getIsOpen() {
        var v = localStorage.getItem(STORAGE_KEY);
        return v === null ? true : v === 'true';
    }

    function getAllPropsUrl(reGroups) {
        for (var i = 0; i < reGroups.length; i++) {
            var a = reGroups[i].querySelector('a[href]');
            if (a) return a.href.split('?')[0];
        }
        var m = window.location.pathname.match(/^(\/dev-admin)/);
        return (m ? m[1] : '') + '/properties';
    }

    function cleanup() {
        var existing = document.querySelector('.bazar-re-wrapper');
        if (!existing) return;
        var children = existing.querySelector('.bazar-re-children');
        if (children) {
            var navGroups = existing.parentNode;
            var next = existing.nextSibling;
            Array.from(children.children).forEach(function (c) {
                navGroups.insertBefore(c, next);
            });
        }
        existing.remove();
    }

    function init() {
        cleanup();

        var navGroups = document.querySelector('ul.fi-sidebar-nav-groups');
        if (!navGroups) return;

        var allGroups = Array.from(navGroups.querySelectorAll(':scope > li.fi-sidebar-group'));
        var reGroups = allGroups.filter(function (g) {
            var lbl = g.getAttribute('data-group-label') || '';
            return TARGET_PREFIXES.some(function (p) { return lbl.startsWith(p); });
        });

        if (reGroups.length === 0) return;

        var total = 0;
        reGroups.forEach(function (g) {
            var m = (g.getAttribute('data-group-label') || '').match(/\((\d+)\)/);
            if (m) total += parseInt(m[1], 10);
        });

        var allPropsUrl = getAllPropsUrl(reGroups);

        var wrapper = document.createElement('li');
        wrapper.className = 'bazar-re-wrapper fi-sidebar-group fi-collapsible';

        wrapper.innerHTML =
            '<div class="fi-sidebar-group-btn bazar-re-btn">' +
                '<a href="' + allPropsUrl + '" class="bazar-re-link">' +
                    '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="bazar-re-icon" style="width:1.25rem;height:1.25rem;flex-shrink:0;" aria-hidden="true">' +
                        '<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008Zm0 3h.008v.008h-.008v-.008Zm0 3h.008v.008h-.008v-.008Z"/>' +
                    '</svg>' +
                    '<span class="fi-sidebar-group-label">Property (' + total + ')</span>' +
                '</a>' +
                '<button type="button" class="bazar-re-arrow-btn" title="Toggle">' +
                    '<svg class="bazar-re-arrow" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">' +
                        '<path fill-rule="evenodd" d="M14.77 12.79a.75.75 0 0 1-1.06-.02L10 8.832 6.29 12.77a.75.75 0 1 1-1.08-1.04l4.25-4.5a.75.75 0 0 1 1.08 0l4.25 4.5a.75.75 0 0 1-.02 1.06z" clip-rule="evenodd"/>' +
                    '</svg>' +
                '</button>' +
            '</div>' +
            '<div class="bazar-re-children"></div>';

        navGroups.insertBefore(wrapper, reGroups[0]);

        var childrenDiv = wrapper.querySelector('.bazar-re-children');
        reGroups.forEach(function (g) { childrenDiv.appendChild(g); });

        function applyState() {
            var open = getIsOpen();
            childrenDiv.style.display = open ? '' : 'none';
            wrapper.querySelector('.bazar-re-arrow').style.transform = open ? 'rotate(0deg)' : 'rotate(180deg)';
            wrapper.classList.toggle('fi-collapsed', !open);
        }

        applyState();

        wrapper.querySelector('.bazar-re-arrow-btn').addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            localStorage.setItem(STORAGE_KEY, !getIsOpen());
            applyState();
        });
    }

    function run() { setTimeout(init, 80); }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }

    document.addEventListener('livewire:navigated', run);
})();
