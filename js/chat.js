/**
 * Bazar Chat Module — REST + polling (no Firebase Firestore needed)
 * Backend: /api/chat/* endpoints in server.py
 */
window.BAZAR_CHAT = (function () {
    'use strict';

    var BASE = '/api/chat';

    /* Build conversation ID from adId + buyerUid */
    function convId(adId, buyerUid) {
        return 'ad' + String(adId) + 'u' + String(buyerUid).replace(/[^a-zA-Z0-9]/g, '').slice(0, 28);
    }

    /* Create or get conversation */
    function ensure(cid, meta) {
        return fetch(BASE + '/ensure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(Object.assign({ conv_id: cid }, meta))
        }).then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); });
    }

    /* Send a message */
    function send(cid, senderId, senderName, text, type) {
        return fetch(BASE + '/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conv_id: cid, sender_id: senderId, sender_name: senderName, text: text, type: type || 'text' })
        }).then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); });
    }

    /* Get messages (since = last seen msg id, 0 = all) */
    function getMsgs(cid, since) {
        return fetch(BASE + '/msgs?conv_id=' + encodeURIComponent(cid) + '&since=' + (since || 0))
            .then(function (r) { return r.ok ? r.json() : { messages: [] }; });
    }

    /* Get conversations for a user */
    function getConvs(uid, sellerName) {
        var url = BASE + '/convs?uid=' + encodeURIComponent(uid || '');
        if (sellerName) url += '&name=' + encodeURIComponent(sellerName);
        var since = localStorage.getItem('bazar_account_since');
        if (since) url += '&since=' + encodeURIComponent(since);
        return fetch(url).then(function (r) { return r.ok ? r.json() : { conversations: [] }; });
    }

    /* Mark conversation as read */
    function markRead(cid, role) {
        return fetch(BASE + '/read', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conv_id: cid, role: role })
        });
    }

    /**
     * Play a short two-tone notification sound via Web Audio API.
     * Skips silently if audio is not available or blocked.
     */
    function playMsgSound() {
        try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            var osc  = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.12);
            gain.gain.setValueAtTime(0.25, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.35);
        } catch (e) {}
    }

    /**
     * Listen to ALL messages in a conversation (load all, then poll for new).
     * opts.myUid — if set, plays a sound when messages from others arrive.
     * Returns object with:
     *   unsub()          — stop polling
     *   pushOptimistic() — immediately render a message before server confirms it
     */
    function listenAllMsgs(cid, cb, opts) {
        var myUid = (opts && opts.myUid) || '';
        var allMsgs = [];
        var lastId = 0;
        var timer = null;
        var _optimisticId = -1;
        var _initialLoaded = false; /* don't play sound for history on first load */

        function applyNew(newMsgs) {
            if (!newMsgs.length) return;
            var hasIncoming = false;
            newMsgs.forEach(function (m) {
                if (m.id > lastId) lastId = m.id;
                var already = allMsgs.some(function (x) { return x.id === m.id; });
                if (!already) {
                    /* remove matching optimistic placeholder if present */
                    var optIdx = -1;
                    for (var i = 0; i < allMsgs.length; i++) {
                        if (allMsgs[i]._optimistic && allMsgs[i].sender_id === m.sender_id && allMsgs[i].text === m.text) {
                            optIdx = i; break;
                        }
                    }
                    if (optIdx !== -1) allMsgs.splice(optIdx, 1);
                    allMsgs.push(m);
                    /* incoming = from someone else, not optimistic */
                    if (myUid && m.sender_id !== myUid && !m._optimistic) hasIncoming = true;
                }
            });
            allMsgs.sort(function (a, b) { return a.id - b.id; });
            cb(allMsgs.slice());
            if (_initialLoaded && hasIncoming) playMsgSound();
        }

        /* Immediately render sender's own message before server round-trip */
        function pushOptimistic(senderId, senderName, text, type) {
            var msg = {
                id: _optimisticId--,
                conv_id: cid,
                sender_id: senderId,
                sender_name: senderName,
                text: text,
                time: Math.floor(Date.now() / 1000),
                type: type || 'text',
                _optimistic: true
            };
            allMsgs.push(msg);
            allMsgs.sort(function (a, b) { return a.id - b.id; });
            cb(allMsgs.slice());
        }

        // Initial full load
        getMsgs(cid, 0).then(function (data) {
            var msgs = data.messages || [];
            if (msgs.length) {
                lastId = msgs[msgs.length - 1].id;
                allMsgs = msgs;
                cb(allMsgs.slice());
            } else {
                cb([]);
            }
            _initialLoaded = true;
        }).catch(function () { cb([]); _initialLoaded = true; });

        // Poll for new messages every 1 second
        timer = setInterval(function () {
            getMsgs(cid, lastId).then(function (data) {
                applyNew(data.messages || []);
            }).catch(function () {});
        }, 1000);

        return {
            unsub: function () { if (timer) clearInterval(timer); },
            pushOptimistic: pushOptimistic
        };
    }

    /**
     * Listen to conversations list.
     * Polls every 2 seconds.
     * cb(conversations_array) called each time.
     */
    function listenConvs(uid, sellerName, cb) {
        var timer = null;

        function poll() {
            getConvs(uid, sellerName).then(function (data) {
                cb(data.conversations || []);
            }).catch(function () {});
        }

        poll(); // immediate first call
        timer = setInterval(poll, 2000);

        return function () { if (timer) clearInterval(timer); };
    }

    return {
        convId: convId,
        ensure: ensure,
        send: send,
        getMsgs: getMsgs,
        listenAllMsgs: listenAllMsgs,
        listenConvs: listenConvs,
        markRead: markRead,
        playMsgSound: playMsgSound
    };
})();
