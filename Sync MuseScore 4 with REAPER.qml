import QtQuick 2.2
import MuseScore 3.0
import MuseScore.Playback 1.0

MuseScore {

    id: root

    title: "Sync with REAPER"

    property var playbackModel: null

    function onMessageToServer(id, msg) {
        let obj = JSON.parse(msg);
        console.log("received message: " + JSON.stringify(obj));
        let reply = getReplyForMessage(obj);
        if (reply == null) return;
        api.websocketserver.send(id, JSON.stringify(reply));
    }

    function onMessageToClient(id, msg) {
        let obj = JSON.parse(msg);
        console.log("received message: " + JSON.stringify(obj));
        let reply = getReplyForMessage(obj);
        if (reply == null) return;
        api.websocket.send(id, JSON.stringify(reply));
    }

    function getReplyForMessage(obj) {
        let playButton = playbackModel.items[1];
        let currentlyPlaying = (playButton.icon === 62409); // Pause icon indicates playing
        if (obj.t === "hello") {
            console.warn("sync: send helloReply");
            return {
                "t": "helloReply",
                "protocol": "musicsync",
                "version": 1,
                "ref": obj.ref,
            };
        } else if (obj.t === "getPlayState") {
            console.log("sync: getPlayState");
            let currentTime = playbackModel.playTime;
            let hours = currentTime.getHours();
            let minutes = currentTime.getMinutes();
            let seconds = currentTime.getSeconds();
            let ms = currentTime.getMilliseconds();
            let pos = hours * 3600 + minutes * 60 + seconds + (ms / 1000);
            return {
                "t": "getPlayStateReply",
                "currentlyPlaying": currentlyPlaying,
                "pos": pos,
                "ref": obj.ref,
            };
        } else if (obj.t == "setPlayState") {
            console.warn("sync: setPlayState");
            if (obj.currentlyPlaying) {
                let pos = obj.pos;
                let newTime = new Date();
                newTime.setHours(Math.floor(pos / 3600));
                newTime.setMinutes(Math.floor((pos % 3600) / 60));
                newTime.setSeconds(Math.floor(pos % 60));
                newTime.setMilliseconds((pos % 1) * 1000);
                playbackModel.playTime = newTime;
                if (!currentlyPlaying) {
                    cmd("play");
                }
            } else if (!obj.currentlyPlaying && currentlyPlaying) {
                // "play" is toggle between play and pause...
                cmd("play");
            }
            return {
                "t": "setPlayStateReply",
                "ok": true,
                "ref": obj.ref,
            };
        }
        return null;
    }

    onRun: {
        console.warn("sync: Loaded");
	playbackModel = Qt.createQmlObject('
	    import MuseScore.Playback 1.0
	    PlaybackToolBarModel {}
	', root, "dynamicPlaybackModel");
	playbackModel.load();

        api.websocketserver.listen(8084, function(id) {
            console.warn("sync: connection from client, id: " + id);
            api.websocketserver.onMessage(id, function (msg) { root.onMessageToServer(id, msg); })
        })
	console.warn("sync: Listening on 8084, connecting to 8085");
        api.websocket.open(8085, function(id) {
            console.warn("sync: connected to server id: " + id);
            api.websocket.onMessage(id, function (msg) { root.onMessageToClient(id, msg); })
        });
    }
}
