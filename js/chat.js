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
     * Listen to ALL messages in a conversation (load all, then poll for new).
     * Returns unsubscribe function.
     * cb(msgs_array) called with full sorted message list each time.
     */
    function listenAllMsgs(cid, cb) {
        var allMsgs = [];
        var lastId = 0;
        var timer = null;

        function applyNew(newMsgs) {
            if (!newMsgs.length) return;
            newMsgs.forEach(function (m) {
                if (m.id > lastId) lastId = m.id;
                allMsgs.push(m);
            });
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
        }).catch(function () { cb([]); });

        // Poll for new messages every 1 second
        timer = setInterval(function () {
            getMsgs(cid, lastId).then(function (data) {
                applyNew(data.messages || []);
            }).catch(function () {});
        }, 1000);

        return function () { if (timer) clearInterval(timer); };
    }

    /**
     * Listen to conversations list.
     * Polls every 5 seconds.
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
        timer = setInterval(poll, 5000);

        return function () { if (timer) clearInterval(timer); };
    }

    return {
        convId: convId,
        ensure: ensure,
        send: send,
        getMsgs: getMsgs,
        listenAllMsgs: listenAllMsgs,
        listenConvs: listenConvs,
        markRead: markRead
    };
})();
