// NReality Multiworld mod. Replaces the base game's final bootstrap action; physics and map bytecode are untouched.
// Everything the mod adds lives in MW. MW.base keeps the original game functions that the mod wraps.
// The client page passes the session as FlashVar _root.mwSession; the mod syncs with it via POST /api/sync.

// ---- Settings of the original bootstrap ----
fscommand("allowscale", "false");
fscommand("showmenu", "false");
APP_GAMETIME_BASETICKLEN = 25;
APP_GAMETIME_TICKLEN = 25;
APP_GAMETIME_SMOOTHAMT = 0;
APP_TILE_SCALE = 12;
APP_NUM_GRIDCOLS = 31;
APP_NUM_GRIDROWS = 23;

MW = new Object();
MW.base = new Object();
MW.EPISODES = 200;
MW.LEVELS = 5;
// Seed, team and slot identity. Without it the mod stays offline and nothing can be played.
MW.session = _root.mwSession;
MW.connected = false;      // the client has answered a sync for this session
MW.menuShown = false;      // the game has finished loading; syncing starts with the main menu
MW.inEpisodeRun = false;   // a normal episode run (not a time trial, demo or replay) is in progress

// ---- NReality maps and a game without online features ----
// The ten NReality map columns (episodes 100-199) are copied into the SWF as vCol10 to vCol19.
MW.base.BuildGameData = NinjaData.prototype.BuildGameData;
NinjaData.prototype.BuildGameData = function() {
    MW.base.BuildGameData.call(this);
    for (var column = 10; column < 20; column++) {
        _root["vCol" + column].call(this);
    }
};
NinjaUserData.prototype.ImportUserData = function() {
    this.shared.data.isImported = true;
};
NinjaUserData.prototype.GetOnlineActive = function() { return false; };
NinjaUserData.prototype.GetPersBestActive = function() { return false; };
// Progress comes from the multiworld, not from the game's own unlocks.
NinjaUserData.prototype.NotifyEpisodeReached = function(num) {};
NinjaUserData.prototype.NotifyEpisodeBeaten = function(num) {};
NinjaUserData.prototype.NotifyLevelReached = function(ep, level) {};
NinjaUserData.prototype.NotifyLevelBeaten = function(ep, level) {};

// ---- Unlocks: only episodes received from the multiworld can be played ----
MW.unlocked = new Object();       // episode -> true
MW.seedEpisodes = new Object();   // episode -> true, the episodes of this seed
MW.seedEpisodeCount = 0;
NinjaUserData.prototype.ValidateEpisodeReached = function(ep) {
    return MW.unlocked[ep] == true;
};
MW.base.LoadEpisodeNum = NinjaData.prototype.LoadEpisodeNum;
NinjaData.prototype.LoadEpisodeNum = function(ep) {
    if (!MW.unlocked[ep]) { return false; }
    return MW.base.LoadEpisodeNum.call(this, ep);
};
NinjaData.prototype.LoadEpisode = function(code) { return false; };

// ---- Checks: the first completion of each level ----
// A check is episode * 5 + level. Pending checks wait in the browser until the client confirms them.
MW.pendingChecks = new Object();     // check -> true
MW.confirmedChecks = new Object();   // check -> true
// Only real episode runs count: no practise mode (it can skip levels), demos or replays.
MW.reportLevelPassed = function() {
    var ep = gamedata.curEpisode;
    var level = gamedata.curLevel;
    if (!MW.inEpisodeRun || !MW.unlocked[ep] || APP_DEBUG_MODE_ACTIVE || APP_IS_PRACTISE || APP_IS_CHEATER) {
        return;
    }
    var check = ep * MW.LEVELS + level;
    if (ep < 0 || ep >= MW.EPISODES || level < 0 || level >= MW.LEVELS || MW.confirmedChecks[check]) { return; }
    MW.pendingChecks[check] = true;
    MW.savePendingChecks();
    trace("MW completion " + ep + ":" + level);
};

// ---- DeathLink ----
// Real deaths in an episode run are reported to the client, which applies amnesty and cooldown.
// Suicides with the kill key never count.
MW.unsentDeaths = 0;
MW.deathCause = "";
// Where the last death happened, for per-level amnesty: the level plus a stamp that changes with every passed level.
MW.deathScope = "";
MW.levelPassStamp = new Date().getTime();
MW.killingForDeathLink = false;
MW.deathLinkKiller = new Object();
MW.deathLinkKiller.name = "DeathLink";
MW.base.KillPlayer = NinjaGame.prototype.KillPlayer;
NinjaGame.prototype.KillPlayer = function(killtype, fx, fy, px, py, obj) {
    var wasAlive = !player.isDead;
    // The exit is tested before fall damage in the same tick, so a level can be passed by a ninja that then dies.
    // The level counts, and the passed event has already left App_Tick_RunningGame: such deaths are not reported.
    var running = TickApp == App_Tick_RunningGame;
    MW.base.KillPlayer.call(this, killtype, fx, fy, px, py, obj);
    if (!wasAlive || !player.isDead) { return; }
    if (MW.killingForDeathLink) { MW.killingForDeathLink = false; return; }
    if (!MW.inEpisodeRun || !running || obj == undefined) { return; }
    if (APP_VOLUNTARY_SUICIDE || APP_IS_PRACTISE || APP_DEBUG_DEATH) { return; }
    MW.unsentDeaths++;
    MW.deathScope = (gamedata.curEpisode * MW.LEVELS + gamedata.curLevel) + "/" + MW.levelPassStamp;
    if (obj != player) { MW.deathCause = "a " + obj.name; }
    else if (killtype == KILLTYPE_FALL && game.playerCurTime <= 0) { MW.deathCause = "running out of time"; }
    else if (killtype == KILLTYPE_FALL) { MW.deathCause = "fall damage"; }
    else { MW.deathCause = "being crushed"; }
};
// A death from another world only hits a ninja that is currently running through a level.
MW.killForDeathLink = function() {
    if (!MW.inEpisodeRun || player.isDead || TickApp != App_Tick_RunningGame) { return; }
    MW.killingForDeathLink = true;
    game.KillPlayer(KILLTYPE_ELECTRIC, 0, -6, player.pos.x, player.pos.y, MW.deathLinkKiller);
};

// ---- Bonus Gold ----
// Each Bonus Gold item adds the time of one gold piece once, to the current episode run. Unlike collected gold it
// also raises the level's start time, so a retry keeps it. Items received outside a run wait for the next one.
MW.bonusGoldReceived = 0;
MW.bonusGoldUsed = 0;
MW.addBonusGoldTime = function() {
    var count = MW.bonusGoldReceived - MW.bonusGoldUsed;
    if (count <= 0 || !MW.inEpisodeRun || APP_IS_PRACTISE) { return; }
    if (TickApp != App_Tick_PreLevelPause && TickApp != App_Tick_RunningGame) { return; }
    game.playerCurTime += count * game.playerBonusTime;
    game.playerStartingTime += count * game.playerBonusTime;
    _global.goldSnd.gotoAndPlay("COLLECTED");
    MW.bonusGoldUsed = MW.bonusGoldReceived;
    MW.saveBonusGoldUsed();
};

// ---- Episode runs ----
MW.base.LevelPassedEvent_Normal = App_LevelPassedEvent_Normal;
App_LevelPassedEvent_Normal = function() {
    MW.levelPassStamp = new Date().getTime();
    MW.reportLevelPassed();
    MW.base.LevelPassedEvent_Normal();
};
MW.base.StartNewGame = App_StartNewGame;
App_StartNewGame = function() {
    if (!MW.connected || !MW.unlocked[gamedata.curEpisode]) { return; }
    MW.inEpisodeRun = true;
    MW.base.StartNewGame();
};
MW.base.StartNewTimeTrial = App_StartNewTimeTrial;
App_StartNewTimeTrial = function(ep, level) {
    if (!MW.unlocked[ep]) { return; }
    MW.inEpisodeRun = false;
    MW.base.StartNewTimeTrial(ep, level);
};
MW.base.StartMainMenu = App_StartMainMenu;
App_StartMainMenu = function() {
    MW.inEpisodeRun = false;
    MW.base.StartMainMenu();
    MW.menuShown = true;
};
// After an episode, continue with the next one of the column only if it is unlocked.
MW.base.PostLevelResponse_NextEpisode = App_PostLevelResponse_NextEpisode;
App_PostLevelResponse_NextEpisode = function() {
    var ep = gamedata.curEpisode;
    var next = gamedata.GetNextEpisodeNum();
    if (next > 0 && Math.floor(next / 10) == Math.floor(ep / 10) && MW.unlocked[next]) {
        MW.base.PostLevelResponse_NextEpisode();
        return;
    }
    APP_KEY_TRIG = false;
    SetActiveProcess(null);
    // Original wording; "continue" leads back to the episode menu here.
    MW.showEpisodeComplete("episode [" + ep + "] complete!!  [spacebar] to continue, [Q] for mainmenu");
    SetActiveProcess(MW.tickEpisodeComplete);
};
MW.showEpisodeComplete = function(text) {
    gui.HideAll();
    gui.Display(_root["GUI_VICTORY" + (1 + Math.floor(Math.random() * 7))]);
    gui.DisplayTextBar(GUI_PASSEDEPISODE);
    gui.AppendToTextBar(text);
};
MW.tickEpisodeComplete = function() {
    App_UpdateGame_Demo(false, false);
    if (APP_KEY_TRIG && (Key.isDown(32) || Key.isDown(81))) {
        var toEpisodeMenu = Key.isDown(32);
        APP_KEY_TRIG = false;
        gui.HideInGame();
        userdata.Save();
        App_LoadMainMenu();
        if (toEpisodeMenu) { App_StartPlayMenu(); }
    }
};

// ---- Episode menu: NReality's 20 columns, showing unlocks and progress ----
MW.isLevelDone = function(check) { return MW.confirmedChecks[check] == true || MW.pendingChecks[check] == true; };
MW.levelsDone = function(ep) {
    var count = 0;
    for (var level = 0; level < MW.LEVELS; level++) {
        if (MW.isLevelDone(ep * MW.LEVELS + level)) { count++; }
    }
    return count;
};
MW.isInSeed = function(ep) { return MW.seedEpisodeCount == 0 || MW.seedEpisodes[ep] == true; };
// Original button frames: 1 = beaten, 2 = hover, 3 = reached but not beaten.
MW.styleEpisodeButton = function(button, ep) {
    var label = ep > 9 ? String(ep) : "0" + ep;
    button._alpha = 100;
    if (MW.unlocked[ep]) {
        button.idleFrame = MW.levelsDone(ep) == MW.LEVELS ? 1 : 3;
        button.gfx.gotoAndStop(button.idleFrame);
        button.num.text = label;
        button.enabled = true;
        button.onRollOver = function() { this.gfx.gotoAndStop(2); };
        button.onRollOut = function() { this.gfx.gotoAndStop(this.idleFrame); };
        button.onReleaseOutside = function() { this.gfx.gotoAndStop(this.idleFrame); };
        button.onRelease = function() { _root.App_PlayEpisodeButtonClicked(this, false); };
    } else {
        button.gfx.gotoAndStop(1);
        // Locked episodes of the seed stay visible but greyed out; others are empty like unreached ones.
        button.num.text = MW.isInSeed(ep) ? label : "";
        if (MW.isInSeed(ep)) { button._alpha = 35; }
        button.enabled = false;
        delete button.onRollOver;
        delete button.onRollOut;
        delete button.onReleaseOutside;
        delete button.onRelease;
    }
};
// Layout from NReality 6g2: the base play menu stretched to 20 columns of ten episodes.
App_StartPlayMenu = function() {
    MW.inEpisodeRun = false;
    gui.Display(GUI_PLAYMENU);
    SetActiveProcess(App_TickPlayMenu);
    var panel = gui.GetCurrentMC().playmenu;
    panel.gfx._xscale = 2200;
    // NReality used getNextHighestDepth(), which SWF 6 content (the base game) does not have.
    for (var ep = 100; ep < MW.EPISODES; ep++) {
        if (panel["e" + ep] == undefined) {
            var copy = panel.e0.duplicateMovieClip("e" + ep, 5000 + ep);
            copy.num.text = "" + ep;
            copy.num._width += 10;
        }
    }
    for (var i = 0; i < MW.EPISODES; i++) {
        var button = panel["e" + i];
        button._x = -320 + Math.floor(i / 10) * 26;
        button._xscale = button._yscale = 100;
        button._y = 25 + (i % 10) * 48;
        button.num.autoSize = true;
        MW.styleEpisodeButton(button, i);
    }
};
MW.refreshPlayMenu = function() {
    var panel = gui.GetCurrentMC().playmenu;
    if (panel == undefined || panel.e199 == undefined) { return; }
    for (var i = 0; i < MW.EPISODES; i++) { MW.styleEpisodeButton(panel["e" + i], i); }
};
App_StartHighscoreMenu = function() { App_StartPlayMenu(); };

// ---- Browser storage ----
// The key names are kept from earlier versions so a player's unconfirmed checks survive updates.
MW.savePendingChecks = function() {
    MW.storage.data.pending = MW.pendingChecks;
    MW.storage.flush();
};
MW.saveBonusGoldUsed = function() {
    MW.storage.data.bonusSpent = MW.bonusGoldUsed;
    MW.storage.flush();
};

// ---- Sync with the client, once per second ----
// Sends: session, pending checks, current episode and level, deaths since the last answer.
// Receives: unlocked episodes, confirmed checks, the seed's episodes, acknowledged deaths, a DeathLink kill and
// the number of Bonus Gold items. Lists are comma separated.
MW.syncInFlight = false;
MW.syncSentAt = 0;
MW.lastUnlocked = "";
MW.lastConfirmed = "";
MW.lastSeedEpisodes = "";
MW.sync = function() {
    if (!MW.menuShown) { return; }
    if (MW.syncInFlight && getTimer() - MW.syncSentAt < 5000) { return; }
    MW.syncInFlight = true;
    MW.syncSentAt = getTimer();
    var request = new LoadVars();
    var answer = new LoadVars();
    request.session = MW.session;
    request.checks = "";
    for (var check in MW.pendingChecks) { request.checks += check + ","; }
    request.episode = MW.inEpisodeRun ? gamedata.curEpisode : -1;
    request.level = MW.inEpisodeRun ? gamedata.curLevel : -1;
    request.mapCount = gamedata.episodeList.length;
    request.deaths = MW.unsentDeaths;
    request.cause = MW.deathCause;
    request.deathScope = MW.deathScope;
    answer.onLoad = function(ok) {
        MW.syncInFlight = false;
        if (!ok || this.session != MW.session) { return; }
        MW.connected = true;
        MW.applySyncAnswer(this);
    };
    request.sendAndLoad("/api/sync", answer, "POST");
};
MW.applySyncAnswer = function(answer) {
    // This runs inside a game frame: rebuild only what changed, save only on change.
    var menuChanged = false;
    if (answer.unlocked != MW.lastUnlocked) {
        MW.lastUnlocked = answer.unlocked;
        MW.unlocked = MW.parseNumberSet(answer.unlocked);
        menuChanged = true;
    }
    if (answer.episodes != MW.lastSeedEpisodes) {
        MW.lastSeedEpisodes = answer.episodes;
        MW.seedEpisodes = MW.parseNumberSet(answer.episodes);
        MW.seedEpisodeCount = 0;
        for (var ep in MW.seedEpisodes) { MW.seedEpisodeCount++; }
        menuChanged = true;
    }
    if (answer.checked != MW.lastConfirmed) {
        MW.lastConfirmed = answer.checked;
        MW.confirmChecks(answer.checked);
        menuChanged = true;
    }
    if (menuChanged) { MW.refreshPlayMenu(); }
    if (Number(answer.deathsAck) > 0) { MW.unsentDeaths = Math.max(0, MW.unsentDeaths - Number(answer.deathsAck)); }
    if (answer.kill == "1") { MW.killForDeathLink(); }
    if (Number(answer.bonusGold) > MW.bonusGoldReceived) { MW.bonusGoldReceived = Number(answer.bonusGold); }
    MW.addBonusGoldTime();
};
MW.parseNumberSet = function(text) {
    var numbers = new Object();
    var parts = text.split(",");
    for (var i = 0; i < parts.length; i++) {
        if (parts[i] != "") { numbers[Number(parts[i])] = true; }
    }
    return numbers;
};
// Confirmed checks no longer need to wait in the browser.
MW.confirmChecks = function(text) {
    MW.confirmedChecks = MW.parseNumberSet(text);
    var removed = false;
    for (var check in MW.confirmedChecks) {
        if (MW.pendingChecks[check] != undefined) {
            delete MW.pendingChecks[check];
            removed = true;
        }
    }
    if (removed) { MW.savePendingChecks(); }
};

// ---- Start ----
InitApp();
if (MW.session != undefined && MW.session != "") {
    MW.storage = SharedObject.getLocal("n_multiworld_pending_" + MW.session, "/");
    if (MW.storage.data.pending != undefined) { MW.pendingChecks = MW.storage.data.pending; }
    if (MW.storage.data.bonusSpent != undefined) { MW.bonusGoldUsed = MW.storage.data.bonusSpent; }
    setInterval(MW.sync, 1000);
    MW.sync();
}
