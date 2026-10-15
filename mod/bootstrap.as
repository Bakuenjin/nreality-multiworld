// Multiworld bootstrap. Existing physics and map bytecode are untouched.
fscommand("allowscale", "false");
fscommand("showmenu", "false");
APP_GAMETIME_BASETICKLEN = 25;
APP_GAMETIME_TICKLEN = 25;
APP_GAMETIME_SMOOTHAMT = 0;
APP_TILE_SCALE = 12;
APP_NUM_GRIDCOLS = 31;
APP_NUM_GRIDROWS = 23;

MW = new Object();
MW.allowed = new Object();
MW.pending = new Object();
MW.done = new Object();
MW.seed = new Object();
MW.seedSize = 0;
// Seed/slot identity from the page (FlashVar). Without it the mod stays offline.
MW.session = _root.mwSession;
MW.active = false;
MW.busy = false;
MW.ready = false;
MW.booted = false;
MW.buildBase = NinjaData.prototype.BuildGameData;
NinjaData.prototype.BuildGameData = function() {
    MW.buildBase.call(this);
    for (var col = 10; col < 20; col++) {
        _root["vCol" + col].call(this);
    }
};
NinjaUserData.prototype.ImportUserData = function() {
    this.shared.data.isImported = true;
};
NinjaUserData.prototype.GetOnlineActive = function() { return false; };
NinjaUserData.prototype.GetPersBestActive = function() { return false; };
NinjaUserData.prototype.NotifyEpisodeReached = function(num) {};
NinjaUserData.prototype.NotifyEpisodeBeaten = function(num) {};
NinjaUserData.prototype.NotifyLevelReached = function(ep, level) {};
NinjaUserData.prototype.NotifyLevelBeaten = function(ep, level) {};
NinjaUserData.prototype.ValidateEpisodeReached = function(ep) {
    return MW.allowed[ep] == true;
};
MW.loadEpisode = NinjaData.prototype.LoadEpisodeNum;
NinjaData.prototype.LoadEpisodeNum = function(ep) {
    if (!MW.allowed[ep]) { return false; }
    return MW.loadEpisode.call(this, ep);
};
NinjaData.prototype.LoadEpisode = function(code) { return false; };

// Only real episode runs count: no practise mode (it can skip levels), demos or replays.
MW.report = function() {
    var ep = gamedata.curEpisode;
    var level = gamedata.curLevel;
    if (!MW.active || !MW.allowed[ep] || APP_DEBUG_MODE_ACTIVE || APP_IS_PRACTISE || APP_IS_CHEATER) {
        return;
    }
    if (ep < 0 || ep >= 200 || level < 0 || level >= 5) { return; }
    MW.pending[ep * 5 + level] = true;
    MW.saved.data.pending = MW.pending;
    MW.saved.flush();
    trace("MW completion " + ep + ":" + level);
};
// DeathLink: real deaths in an episode run are reported, suicides (kill key) never.
MW.deaths = 0;
MW.deathCause = "";
MW.linkKill = false;
MW.linkKiller = new Object();
MW.linkKiller.name = "DeathLink";
MW.killPlayer = NinjaGame.prototype.KillPlayer;
NinjaGame.prototype.KillPlayer = function(killtype, fx, fy, px, py, obj) {
    var wasAlive = !player.isDead;
    MW.killPlayer.call(this, killtype, fx, fy, px, py, obj);
    if (!wasAlive || !player.isDead) { return; }
    if (MW.linkKill) { MW.linkKill = false; return; }
    if (!MW.active || obj == undefined || APP_VOLUNTARY_SUICIDE || APP_IS_PRACTISE || APP_DEBUG_DEATH) { return; }
    MW.deaths++;
    if (obj != player) { MW.deathCause = "a " + obj.name; }
    else if (killtype == KILLTYPE_FALL && game.playerCurTime <= 0) { MW.deathCause = "running out of time"; }
    else if (killtype == KILLTYPE_FALL) { MW.deathCause = "fall damage"; }
    else { MW.deathCause = "being crushed"; }
};
// A death from another world only hits a ninja that is currently running through a level.
MW.receiveDeath = function() {
    if (!MW.active || player.isDead || TickApp != App_Tick_RunningGame) { return; }
    MW.linkKill = true;
    game.KillPlayer(KILLTYPE_ELECTRIC, 0, -6, player.pos.x, player.pos.y, MW.linkKiller);
};
MW.normalPassed = App_LevelPassedEvent_Normal;
App_LevelPassedEvent_Normal = function() {
    MW.report();
    MW.normalPassed();
};

MW.showPassedEpisode = function(text) {
    gui.HideAll();
    gui.Display(_root["GUI_VICTORY" + (1 + Math.floor(Math.random() * 7))]);
    gui.DisplayTextBar(GUI_PASSEDEPISODE);
    gui.AppendToTextBar(text);
};
MW.tickPassedEpisode = function() {
    App_UpdateGame_Demo(false, false);
    if (APP_KEY_TRIG && (Key.isDown(32) || Key.isDown(81))) {
        var toEpisodes = Key.isDown(32);
        APP_KEY_TRIG = false;
        gui.HideInGame();
        userdata.Save();
        App_LoadMainMenu();
        if (toEpisodes) { App_StartPlayMenu(); }
    }
};
// Continue with the next episode of the column only if it is unlocked; nothing is unlocked automatically.
MW.nextEpisode = App_PostLevelResponse_NextEpisode;
App_PostLevelResponse_NextEpisode = function() {
    var ep = gamedata.curEpisode;
    var next = gamedata.GetNextEpisodeNum();
    if (next > 0 && Math.floor(next / 10) == Math.floor(ep / 10) && MW.allowed[next]) {
        MW.nextEpisode();
        return;
    }
    APP_KEY_TRIG = false;
    SetActiveProcess(null);
    // Original wording; "continue" leads back to the episode menu here.
    MW.showPassedEpisode("episode [" + ep + "] complete!!  [spacebar] to continue, [Q] for mainmenu");
    SetActiveProcess(MW.tickPassedEpisode);
};
MW.mainMenu = App_StartMainMenu;
App_StartMainMenu = function() {
    MW.active = false;
    MW.mainMenu();
    MW.booted = true;
};

MW.startTrial = App_StartNewTimeTrial;
App_StartNewTimeTrial = function(ep, level) {
    if (!MW.allowed[ep]) { return; }
    MW.active = false;
    MW.startTrial(ep, level);
};
MW.startNormal = App_StartNewGame;
App_StartNewGame = function() {
    if (!MW.ready || !MW.allowed[gamedata.curEpisode]) { return; }
    MW.active = true;
    MW.startNormal();
};

MW.isDone = function(check) { return MW.done[check] == true || MW.pending[check] == true; };
MW.doneCount = function(ep) {
    var count = 0;
    for (var level = 0; level < 5; level++) { if (MW.isDone(ep * 5 + level)) { count++; } }
    return count;
};
MW.inSeed = function(ep) { return MW.seedSize == 0 || MW.seed[ep] == true; };
// Original button states: frame 1 = beaten, 2 = hover, 3 = reached but not beaten.
MW.styleEpisodeButton = function(but, ep) {
    var label = ep > 9 ? String(ep) : "0" + ep;
    but._alpha = 100;
    if (MW.allowed[ep]) {
        but.idleFrame = MW.doneCount(ep) == 5 ? 1 : 3;
        but.gfx.gotoAndStop(but.idleFrame);
        but.num.text = label;
        but.enabled = true;
        but.onRollOver = function() { this.gfx.gotoAndStop(2); };
        but.onRollOut = function() { this.gfx.gotoAndStop(this.idleFrame); };
        but.onReleaseOutside = function() { this.gfx.gotoAndStop(this.idleFrame); };
        but.onRelease = function() { _root.App_PlayEpisodeButtonClicked(this, false); };
    } else {
        but.gfx.gotoAndStop(1);
        // Locked episodes of the seed stay visible but greyed out; others are empty like unreached ones.
        but.num.text = MW.inSeed(ep) ? label : "";
        if (MW.inSeed(ep)) { but._alpha = 35; }
        but.enabled = false;
        delete but.onRollOver;
        delete but.onRollOut;
        delete but.onReleaseOutside;
        delete but.onRelease;
    }
};
// Layout from NReality 6g2: the base play menu stretched to 20 columns of ten episodes.
App_StartPlayMenu = function() {
    MW.active = false;
    gui.Display(GUI_PLAYMENU);
    SetActiveProcess(App_TickPlayMenu);
    var menuMC = gui.GetCurrentMC();
    var panel = menuMC.playmenu;
    panel.gfx._xscale = 2200;
    // NReality used getNextHighestDepth(), which SWF 6 content (the base game) does not have.
    for (var j = 100; j < 200; j++) {
        if (panel["e" + j] == undefined) {
            var copy = panel.e0.duplicateMovieClip("e" + j, 5000 + j);
            copy.num.text = "" + j;
            copy.num._width += 10;
        }
    }
    for (var i = 0; i < 200; i++) {
        var but = panel["e" + i];
        but._x = -320 + Math.floor(i / 10) * 26;
        but._xscale = but._yscale = 100;
        but._y = 25 + (i % 10) * 48;
        but.num.autoSize = true;
        MW.styleEpisodeButton(but, i);
    }
};
MW.refreshPlayMenu = function() {
    var panel = gui.GetCurrentMC().playmenu;
    if (panel == undefined || panel.e199 == undefined) { return; }
    for (var i = 0; i < 200; i++) { MW.styleEpisodeButton(panel["e" + i], i); }
};

App_StartHighscoreMenu = function() { App_StartPlayMenu(); };

MW.poll = function() {
    if (!MW.booted) { return; }
    if (MW.busy && getTimer() - MW.sentAt < 5000) { return; }
    MW.busy = true;
    MW.sentAt = getTimer();
    var send = new LoadVars();
    var receive = new LoadVars();
    send.session = MW.session;
    send.checks = "";
    for (var key in MW.pending) { send.checks += key + ","; }
    send.episode = MW.active ? gamedata.curEpisode : -1;
    send.level = MW.active ? gamedata.curLevel : -1;
    send.mapCount = gamedata.episodeList.length;
    send.deaths = MW.deaths;
    send.cause = MW.deathCause;
    receive.onLoad = function(ok) {
        MW.busy = false;
        if (!ok || this.session != MW.session) { return; }
        MW.ready = true;
        var previous = MW.unlockText + "|" + MW.checkedText + "|" + MW.episodesText;
        MW.unlockText = this.unlocked;
        MW.checkedText = this.checked;
        MW.episodesText = this.episodes;
        MW.allowed = new Object();
        var list = this.unlocked.split(",");
        for (var i = 0; i < list.length; i++) {
            if (list[i] != "") { MW.allowed[Number(list[i])] = true; }
        }
        MW.seed = new Object();
        MW.seedSize = 0;
        var eps = this.episodes.split(",");
        for (var k = 0; k < eps.length; k++) {
            if (eps[k] != "") { MW.seed[Number(eps[k])] = true; MW.seedSize++; }
        }
        MW.done = new Object();
        var ack = this.checked.split(",");
        for (var j = 0; j < ack.length; j++) {
            if (ack[j] != "") { MW.done[Number(ack[j])] = true; }
            delete MW.pending[ack[j]];
        }
        MW.saved.data.pending = MW.pending;
        MW.saved.flush();
        if (previous != MW.unlockText + "|" + MW.checkedText + "|" + MW.episodesText) { MW.refreshPlayMenu(); }
        if (Number(this.deathsAck) > 0) { MW.deaths = Math.max(0, MW.deaths - Number(this.deathsAck)); }
        if (this.kill == "1") { MW.receiveDeath(); }
    };
    send.sendAndLoad("/api/sync", receive, "POST");
};
InitApp();
if (MW.session != undefined && MW.session != "") {
    MW.saved = SharedObject.getLocal("n_multiworld_pending_" + MW.session, "/");
    if (MW.saved.data.pending != undefined) { MW.pending = MW.saved.data.pending; }
    setInterval(MW.poll, 1000);
    MW.poll();
}
