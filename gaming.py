from datetime import datetime
from flask import render_template, request, session, redirect, url_for, flash
from sqlalchemy import or_, func, and_
from werkzeug.security import generate_password_hash

def register_gaming(app, db, User):
    # Keep registration idempotent for pytest imports and development reloads.
    if getattr(app, "_kharidino_gaming_registered", False):
        return getattr(app, "_kharidino_gaming_seed", None)

    class GamingGame(db.Model):
        __tablename__ = "gaming_game"
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(160), nullable=False)
        slug = db.Column(db.String(180), nullable=False, unique=True)
        platform = db.Column(db.String(40), default="PC")
        genre = db.Column(db.String(80), default="")
        mode = db.Column(db.String(80), default="")
        description = db.Column(db.Text, default="")
        cover = db.Column(db.String(500), default="")
        publisher = db.Column(db.String(160), default="")
        release_year = db.Column(db.Integer, default=2026)
        active = db.Column(db.Boolean, default=True)

    class GamerProfile(db.Model):
        __tablename__ = "gaming_profile"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
        gamer_tag = db.Column(db.String(80), unique=True, nullable=False)
        bio = db.Column(db.Text, default="")
        platform = db.Column(db.String(40), default="PC")
        city = db.Column(db.String(80), default="")
        level = db.Column(db.Integer, default=1)
        xp = db.Column(db.Integer, default=0)
        reputation = db.Column(db.Integer, default=100)
        status = db.Column(db.String(30), default="online")
        avatar = db.Column(db.String(500), default="")
        favorite_games = db.Column(db.Text, default="")
        last_seen = db.Column(db.DateTime, default=datetime.utcnow)
        user = db.relationship("User", backref=db.backref("gaming_profile", uselist=False))

    class GamerFriend(db.Model):
        __tablename__ = "gaming_friend"
        id = db.Column(db.Integer, primary_key=True)
        requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        addressee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        status = db.Column(db.String(20), default="pending")
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        __table_args__ = (db.UniqueConstraint("requester_id", "addressee_id", name="uq_gaming_friend_pair"),)

    class GamerFollow(db.Model):
        __tablename__ = "gaming_follow"
        id = db.Column(db.Integer, primary_key=True)
        follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        __table_args__ = (db.UniqueConstraint("follower_id", "followed_id", name="uq_gaming_follow"),)

    class GamingTeam(db.Model):
        __tablename__ = "gaming_team"
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(120), nullable=False)
        tag = db.Column(db.String(30), default="")
        game = db.Column(db.String(120), default="")
        platform = db.Column(db.String(40), default="")
        rank = db.Column(db.String(60), default="")
        city = db.Column(db.String(80), default="")
        description = db.Column(db.Text, default="")
        owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
        verified = db.Column(db.Boolean, default=False)
        wins = db.Column(db.Integer, default=0)
        reputation = db.Column(db.Integer, default=100)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingPlayerItem(db.Model):
        __tablename__ = "gaming_player_item"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        name = db.Column(db.String(120), nullable=False)
        rarity = db.Column(db.String(40), default="Rare")
        icon = db.Column(db.String(20), default="🎮")
        description = db.Column(db.String(300), default="")
        equipped = db.Column(db.Boolean, default=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingTeamMember(db.Model):
        __tablename__ = "gaming_team_member"
        id = db.Column(db.Integer, primary_key=True)
        team_id = db.Column(db.Integer, db.ForeignKey("gaming_team.id"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        role = db.Column(db.String(30), default="member")
        joined_at = db.Column(db.DateTime, default=datetime.utcnow)
        __table_args__ = (db.UniqueConstraint("team_id", "user_id", name="uq_gaming_team_member"),)

    class GamingPost(db.Model):
        __tablename__ = "gaming_post"
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(180), nullable=False)
        body = db.Column(db.Text, default="")
        game = db.Column(db.String(120), default="")
        post_type = db.Column(db.String(40), default="discussion")
        author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
        likes_count = db.Column(db.Integer, default=0)
        comments_count = db.Column(db.Integer, default=0)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingLike(db.Model):
        __tablename__ = "gaming_like"
        id = db.Column(db.Integer, primary_key=True)
        post_id = db.Column(db.Integer, db.ForeignKey("gaming_post.id"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        __table_args__ = (db.UniqueConstraint("post_id", "user_id", name="uq_gaming_like"),)

    class GamingComment(db.Model):
        __tablename__ = "gaming_comment"
        id = db.Column(db.Integer, primary_key=True)
        post_id = db.Column(db.Integer, db.ForeignKey("gaming_post.id"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        body = db.Column(db.Text, nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingGameStat(db.Model):
        __tablename__ = "gaming_game_stat"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        game = db.Column(db.String(160), nullable=False)
        platform = db.Column(db.String(40), default="PC")
        rank = db.Column(db.String(80), default="")
        wins = db.Column(db.Integer, default=0)
        losses = db.Column(db.Integer, default=0)
        hours = db.Column(db.Integer, default=0)
        mmr = db.Column(db.Integer, default=0)
        __table_args__ = (db.UniqueConstraint("user_id", "game", "platform", name="uq_gaming_game_stat"),)

    class MatchmakingRequest(db.Model):
        __tablename__ = "gaming_match_request"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        game = db.Column(db.String(160), nullable=False)
        platform = db.Column(db.String(40), default="PC")
        rank = db.Column(db.String(80), default="")
        mode = db.Column(db.String(80), default="Squad")
        language = db.Column(db.String(80), default="فارسی")
        play_time = db.Column(db.String(120), default="")
        party_size = db.Column(db.Integer, default=1)
        mic_required = db.Column(db.Boolean, default=False)
        city = db.Column(db.String(80), default="")
        status = db.Column(db.String(30), default="open")
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingTournament(db.Model):
        __tablename__ = "gaming_tournament"
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(180), nullable=False)
        game = db.Column(db.String(120), default="")
        platform = db.Column(db.String(40), default="")
        prize = db.Column(db.String(120), default="")
        status = db.Column(db.String(40), default="ثبت‌نام باز")
        date_text = db.Column(db.String(80), default="")
        description = db.Column(db.Text, default="")
        max_players = db.Column(db.Integer, default=32)
        participants_count = db.Column(db.Integer, default=0)

    class TournamentParticipant(db.Model):
        __tablename__ = "gaming_tournament_participant"
        id = db.Column(db.Integer, primary_key=True)
        tournament_id = db.Column(db.Integer, db.ForeignKey("gaming_tournament.id"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        seed = db.Column(db.Integer, default=0)
        score = db.Column(db.Integer, default=0)
        result = db.Column(db.String(40), default="registered")
        __table_args__ = (db.UniqueConstraint("tournament_id", "user_id", name="uq_gaming_tournament_player"),)

    class GamingAchievement(db.Model):
        __tablename__ = "gaming_achievement"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        code = db.Column(db.String(80), nullable=False)
        title = db.Column(db.String(160), nullable=False)
        description = db.Column(db.String(300), default="")
        xp = db.Column(db.Integer, default=0)
        earned_at = db.Column(db.DateTime, default=datetime.utcnow)
        __table_args__ = (db.UniqueConstraint("user_id", "code", name="uq_gaming_achievement"),)

    class GamingNotification(db.Model):
        __tablename__ = "gaming_notification"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        title = db.Column(db.String(180), nullable=False)
        body = db.Column(db.String(500), default="")
        kind = db.Column(db.String(40), default="system")
        read = db.Column(db.Boolean, default=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingReport(db.Model):
        __tablename__ = "gaming_report"
        id = db.Column(db.Integer, primary_key=True)
        reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        target_type = db.Column(db.String(40), nullable=False)
        target_id = db.Column(db.Integer, nullable=False)
        reason = db.Column(db.String(120), nullable=False)
        details = db.Column(db.Text, default="")
        status = db.Column(db.String(30), default="open")
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def logged_user():
        uid = session.get("user_id")
        return db.session.get(User, uid) if uid else None

    def ensure_profile(user_id):
        p = GamerProfile.query.filter_by(user_id=user_id).first()
        if p:
            return p
        user = db.session.get(User, user_id)
        base = (getattr(user, "name", "Gamer") or "Gamer").strip() or "Gamer"
        tag = base.replace(" ", "_")[:55]
        suffix = 1
        while GamerProfile.query.filter_by(gamer_tag=tag).first():
            suffix += 1
            tag = f"{base.replace(' ', '_')[:48]}_{suffix}"
        p = GamerProfile(user_id=user_id, gamer_tag=tag)
        db.session.add(p)
        db.session.commit()
        return p

    def xp_level(xp):
        return max(1, int((xp or 0) // 500) + 1)

    app.jinja_env.globals["gaming_game_model"] = GamingGame
    app.jinja_env.globals["gaming_profile_model"] = GamerProfile


    # --- Gaming 3.0: platform identity, quests, wallet/rewards, clips, guides, seasons, leagues ---
    class GamingPlatformAccount(db.Model):
        __tablename__ = "gaming_platform_account"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        platform = db.Column(db.String(40), nullable=False)
        external_tag = db.Column(db.String(120), nullable=False)
        verified = db.Column(db.Boolean, default=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        __table_args__ = (db.UniqueConstraint("platform","external_tag",name="uq_gaming_platform_identity"),)

    class GamingQuest(db.Model):
        __tablename__ = "gaming_quest"
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(180), nullable=False)
        description = db.Column(db.String(500), default="")
        xp = db.Column(db.Integer, default=100)
        reward_points = db.Column(db.Integer, default=0)
        kind = db.Column(db.String(40), default="weekly")
        active = db.Column(db.Boolean, default=True)

    class GamingQuestProgress(db.Model):
        __tablename__ = "gaming_quest_progress"
        id = db.Column(db.Integer, primary_key=True)
        quest_id = db.Column(db.Integer, db.ForeignKey("gaming_quest.id"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        progress = db.Column(db.Integer, default=0)
        completed = db.Column(db.Boolean, default=False)
        claimed = db.Column(db.Boolean, default=False)
        __table_args__ = (db.UniqueConstraint("quest_id","user_id",name="uq_gaming_quest_user"),)

    class GamingRewardWallet(db.Model):
        __tablename__ = "gaming_reward_wallet"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
        points = db.Column(db.Integer, default=0)
        lifetime_earned = db.Column(db.Integer, default=0)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingClip(db.Model):
        __tablename__ = "gaming_clip"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        game = db.Column(db.String(160), default="")
        title = db.Column(db.String(180), nullable=False)
        url = db.Column(db.String(700), nullable=False)
        thumbnail = db.Column(db.String(700), default="")
        views = db.Column(db.Integer, default=0)
        likes = db.Column(db.Integer, default=0)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingGuide(db.Model):
        __tablename__ = "gaming_guide"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        game = db.Column(db.String(160), nullable=False)
        title = db.Column(db.String(180), nullable=False)
        body = db.Column(db.Text, default="")
        tags = db.Column(db.String(500), default="")
        views = db.Column(db.Integer, default=0)
        helpful = db.Column(db.Integer, default=0)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingSeason(db.Model):
        __tablename__ = "gaming_season"
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(120), nullable=False)
        start_at = db.Column(db.DateTime, default=datetime.utcnow)
        end_at = db.Column(db.DateTime, nullable=True)
        active = db.Column(db.Boolean, default=True)

    class GamingLeague(db.Model):
        __tablename__ = "gaming_league"
        id = db.Column(db.Integer, primary_key=True)
        season_id = db.Column(db.Integer, db.ForeignKey("gaming_season.id"), nullable=True)
        name = db.Column(db.String(160), nullable=False)
        game = db.Column(db.String(160), default="")
        platform = db.Column(db.String(40), default="")
        tier = db.Column(db.String(50), default="Open")
        teams_count = db.Column(db.Integer, default=0)
        prize = db.Column(db.String(120), default="")

    class GamingClanWar(db.Model):
        __tablename__ = "gaming_clan_war"
        id = db.Column(db.Integer, primary_key=True)
        season_id = db.Column(db.Integer, db.ForeignKey("gaming_season.id"), nullable=True)
        team_a_id = db.Column(db.Integer, db.ForeignKey("gaming_team.id"), nullable=False)
        team_b_id = db.Column(db.Integer, db.ForeignKey("gaming_team.id"), nullable=False)
        score_a = db.Column(db.Integer, default=0)
        score_b = db.Column(db.Integer, default=0)
        status = db.Column(db.String(30), default="scheduled")
        scheduled_at = db.Column(db.DateTime, nullable=True)

    class GamingParty(db.Model):
        __tablename__ = "gaming_party"
        id = db.Column(db.Integer, primary_key=True)
        owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        game = db.Column(db.String(160), nullable=False)
        platform = db.Column(db.String(40), default="PC")
        mode = db.Column(db.String(80), default="Squad")
        max_members = db.Column(db.Integer, default=4)
        status = db.Column(db.String(30), default="open")
        voice_enabled = db.Column(db.Boolean, default=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingPartyMember(db.Model):
        __tablename__ = "gaming_party_member"
        id = db.Column(db.Integer, primary_key=True)
        party_id = db.Column(db.Integer, db.ForeignKey("gaming_party.id"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        joined_at = db.Column(db.DateTime, default=datetime.utcnow)
        __table_args__ = (db.UniqueConstraint("party_id","user_id",name="uq_gaming_party_member"),)

    class GamingModerationAction(db.Model):
        __tablename__ = "gaming_moderation_action"
        id = db.Column(db.Integer, primary_key=True)
        report_id = db.Column(db.Integer, db.ForeignKey("gaming_report.id"), nullable=True)
        moderator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
        action = db.Column(db.String(60), nullable=False)
        note = db.Column(db.String(500), default="")
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @app.get("/gaming/arena")
    def gaming_arena():
        season = GamingSeason.query.filter_by(active=True).order_by(GamingSeason.id.desc()).first()
        leagues = GamingLeague.query.order_by(GamingLeague.teams_count.desc()).limit(20).all()
        wars = GamingClanWar.query.order_by(GamingClanWar.id.desc()).limit(20).all()
        return render_template("gaming/arena.html", season=season, leagues=leagues, wars=wars)

    @app.get("/gaming/quests")
    def gaming_quests():
        user = logged_user()
        quests = GamingQuest.query.filter_by(active=True).order_by(GamingQuest.id.desc()).all()
        progress = {p.quest_id:p for p in GamingQuestProgress.query.filter_by(user_id=user.id).all()} if user else {}
        wallet = GamingRewardWallet.query.filter_by(user_id=user.id).first() if user else None
        return render_template("gaming/quests.html", quests=quests, progress=progress, wallet=wallet)

    @app.post("/gaming/quests/<int:quest_id>/claim")
    def gaming_quest_claim(quest_id):
        user = logged_user()
        if not user: return redirect(url_for("login", next="/gaming/quests"))
        q = db.session.get(GamingQuest, quest_id)
        if not q: return redirect(url_for("gaming_quests"))
        p = GamingQuestProgress.query.filter_by(quest_id=quest_id,user_id=user.id).first()
        if not p or not p.completed or p.claimed: return redirect(url_for("gaming_quests"))
        p.claimed = True
        profile = ensure_profile(user.id); profile.xp += q.xp; profile.level = xp_level(profile.xp)
        wallet = GamingRewardWallet.query.filter_by(user_id=user.id).first()
        if not wallet: wallet = GamingRewardWallet(user_id=user.id); db.session.add(wallet)
        wallet.points += q.reward_points; wallet.lifetime_earned += q.reward_points
        db.session.commit()
        return redirect(url_for("gaming_quests"))

    @app.get("/gaming/party")
    def gaming_party():
        parties = GamingParty.query.filter_by(status="open").order_by(GamingParty.id.desc()).limit(50).all()
        games = GamingGame.query.filter_by(active=True).order_by(GamingGame.name).all()
        return render_template("gaming/party.html", parties=parties, games=games)

    @app.post("/gaming/party/create")
    def gaming_party_create():
        user = logged_user()
        if not user: return redirect(url_for("login", next="/gaming/party"))
        game = request.form.get("game","").strip()[:160]
        if not game:
            flash("نام بازی الزامی است.", "danger")
            return redirect(url_for("gaming_party"))
        try:
            max_members = max(2, min(10, int(request.form.get("max_members", 4) or 4)))
        except (TypeError, ValueError):
            max_members = 4
        party = GamingParty(owner_id=user.id, game=game,
            platform=request.form.get("platform","PC").strip()[:40], mode=request.form.get("mode","Squad").strip()[:80],
            max_members=max_members, voice_enabled=bool(request.form.get("voice_enabled")))
        db.session.add(party); db.session.flush()
        db.session.add(GamingPartyMember(party_id=party.id,user_id=user.id))
        db.session.commit()
        return redirect(url_for("gaming_party"))

    @app.post("/gaming/party/<int:party_id>/join")
    def gaming_party_join(party_id):
        user=logged_user()
        if not user: return redirect(url_for("login",next="/gaming/party"))
        party=db.session.get(GamingParty,party_id)
        if not party or party.status!="open": return redirect(url_for("gaming_party"))
        if not GamingPartyMember.query.filter_by(party_id=party_id,user_id=user.id).first():
            count=GamingPartyMember.query.filter_by(party_id=party_id).count()
            if count < party.max_members:
                db.session.add(GamingPartyMember(party_id=party_id,user_id=user.id))
                if count+1 >= party.max_members: party.status="full"
                db.session.commit()
        return redirect(url_for("gaming_party"))

    @app.post("/gaming/platform/connect")
    def gaming_platform_connect():
        user=logged_user()
        if not user: return redirect(url_for("login",next="/gaming"))
        platform=request.form.get("platform","").strip()[:40]; tag=request.form.get("external_tag","").strip()[:120]
        if platform and tag:
            existing = GamingPlatformAccount.query.filter_by(user_id=user.id, platform=platform).first()
            if existing:
                existing.external_tag = tag
            else:
                conflict = GamingPlatformAccount.query.filter_by(platform=platform, external_tag=tag).first()
                if not conflict:
                    db.session.add(GamingPlatformAccount(user_id=user.id,platform=platform,external_tag=tag))
            db.session.commit()
        return redirect(request.referrer or url_for("gaming"))

    @app.post("/gaming/clip/create")
    def gaming_clip_create():
        user=logged_user()
        if not user: return redirect(url_for("login",next="/gaming/club"))
        title=request.form.get("title","").strip(); url=request.form.get("url","").strip()
        if title and url:
            db.session.add(GamingClip(user_id=user.id,game=request.form.get("game",""),title=title,url=url,thumbnail=request.form.get("thumbnail","")))
            db.session.commit()
        return redirect(request.referrer or url_for("gaming_club"))

    @app.get("/gaming")
    def gaming():
        q = request.args.get("q", "").strip()
        platform = request.args.get("platform", "").strip()
        genre = request.args.get("genre", "").strip()
        mode = request.args.get("mode", "").strip()
        sort = request.args.get("sort", "popular").strip()
        query = GamingGame.query.filter_by(active=True)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(GamingGame.name.ilike(like), GamingGame.description.ilike(like)))
        if platform: query = query.filter_by(platform=platform)
        if genre: query = query.filter_by(genre=genre)
        if mode: query = query.filter_by(mode=mode)
        games = query.order_by(GamingGame.name.asc() if sort == "name" else GamingGame.id.desc()).all()
        teams = GamingTeam.query.order_by(GamingTeam.wins.desc(), GamingTeam.reputation.desc()).limit(8).all()
        tournaments = GamingTournament.query.order_by(GamingTournament.id.desc()).limit(6).all()
        posts = GamingPost.query.order_by(GamingPost.id.desc()).limit(8).all()
        leaderboard = GamerProfile.query.order_by(GamerProfile.level.desc(), GamerProfile.reputation.desc()).limit(10).all()
        return render_template("gaming/index.html", games=games, teams=teams, tournaments=tournaments, posts=posts,
                               leaderboard=leaderboard, q=q, platform=platform, genre=genre, mode=mode, sort=sort)

    @app.get("/gaming/club")
    def gaming_club():
        posts = GamingPost.query.order_by(GamingPost.id.desc()).limit(40).all()
        teams = GamingTeam.query.order_by(GamingTeam.reputation.desc()).limit(12).all()
        tournaments = GamingTournament.query.order_by(GamingTournament.id.desc()).limit(8).all()
        return render_template("gaming/club.html", teams=teams, posts=posts, tournaments=tournaments)

    @app.get("/gaming/teams")
    def gaming_teams():
        game = request.args.get("game", "").strip()
        platform = request.args.get("platform", "").strip()
        rank = request.args.get("rank", "").strip()
        city = request.args.get("city", "").strip()
        query = GamingTeam.query
        if game: query = query.filter_by(game=game)
        if platform: query = query.filter_by(platform=platform)
        if rank: query = query.filter_by(rank=rank)
        if city: query = query.filter_by(city=city)
        return render_template("gaming/teams.html", teams=query.order_by(GamingTeam.reputation.desc()).all(),
                               game=game, platform=platform, rank=rank, city=city)

    @app.get("/gaming/matchmaking")
    def gaming_matchmaking():
        games = GamingGame.query.filter_by(active=True).order_by(GamingGame.name).all()
        requests_list = MatchmakingRequest.query.filter_by(status="open").order_by(MatchmakingRequest.id.desc()).limit(60).all()
        return render_template("gaming/matchmaking.html", games=games, requests_list=requests_list)

    @app.get("/gaming/tournaments")
    def gaming_tournaments():
        return render_template("gaming/tournaments.html", tournaments=GamingTournament.query.order_by(GamingTournament.id.desc()).all())

    @app.get("/gaming/leaderboard")
    def gaming_leaderboard():
        profiles = GamerProfile.query.order_by(GamerProfile.level.desc(), GamerProfile.xp.desc(), GamerProfile.reputation.desc()).limit(100).all()
        teams = GamingTeam.query.order_by(GamingTeam.wins.desc(), GamingTeam.reputation.desc()).limit(50).all()
        return render_template("gaming/leaderboard.html", profiles=profiles, teams=teams)

    @app.get("/gaming/profile/<gamer_tag>")
    def gaming_profile(gamer_tag):
        profile = GamerProfile.query.filter_by(gamer_tag=gamer_tag).first_or_404()
        stats = GamingGameStat.query.filter_by(user_id=profile.user_id).order_by(GamingGameStat.mmr.desc()).all()
        achievements = GamingAchievement.query.filter_by(user_id=profile.user_id).order_by(GamingAchievement.earned_at.desc()).all()
        followers = GamerFollow.query.filter_by(followed_id=profile.user_id).count()
        following = GamerFollow.query.filter_by(follower_id=profile.user_id).count()
        teams = GamingTeamMember.query.filter_by(user_id=profile.user_id).all()\n        player_items = GamingPlayerItem.query.filter_by(user_id=profile.user_id).order_by(GamingPlayerItem.id.desc()).all()
        is_following = bool(logged_user() and GamerFollow.query.filter_by(follower_id=logged_user().id, followed_id=profile.user_id).first())
        return render_template("gaming/profile.html", profile=profile, stats=stats, achievements=achievements,
                               followers=followers, following=following, teams=teams, player_items=player_items, is_following=is_following)

    @app.get("/gaming/game/<slug>")
    def gaming_game(slug):
        game = GamingGame.query.filter_by(slug=slug, active=True).first_or_404()
        related = GamingGame.query.filter(GamingGame.id != game.id, GamingGame.platform == game.platform).limit(8).all()
        teams = GamingTeam.query.filter_by(game=game.name).order_by(GamingTeam.wins.desc()).limit(12).all()
        posts = GamingPost.query.filter_by(game=game.name).order_by(GamingPost.id.desc()).limit(20).all()
        products = []
        try:
            Product = app.view_functions.get("home") and db.Model.registry._class_registry.get("Product")
            if Product:
                products = Product.query.filter(Product.name.ilike(f"%{game.name}%")).limit(8).all()
        except Exception:
            products = []
        return render_template("gaming/game.html", game=game, related=related, teams=teams, posts=posts, products=products)

    @app.post("/gaming/profile/setup")
    def gaming_profile_setup():
        user = logged_user()
        if not user:
            flash("برای ساخت پروفایل گیمر وارد حساب شوید.", "warning")
            return redirect(url_for("login", next="/gaming"))
        p = ensure_profile(user.id)
        requested_tag = request.form.get("gamer_tag", p.gamer_tag).strip()[:80] or p.gamer_tag
        if requested_tag != p.gamer_tag and GamerProfile.query.filter_by(gamer_tag=requested_tag).first():
            flash("این Gamer Tag قبلاً استفاده شده است.", "danger")
            return redirect(url_for("gaming_profile", gamer_tag=p.gamer_tag))
        p.gamer_tag = requested_tag
        p.bio = request.form.get("bio", "").strip()
        p.platform = request.form.get("platform", "PC").strip()
        p.city = request.form.get("city", "").strip()[:80]
        p.favorite_games = request.form.get("favorite_games", "").strip()
        p.status = request.form.get("status", "online").strip()
        db.session.commit()
        flash("پروفایل گیمر شما به‌روزرسانی شد.", "success")
        return redirect(url_for("gaming_profile", gamer_tag=p.gamer_tag))

    @app.post("/gaming/follow/<int:user_id>")
    def gaming_follow(user_id):
        user = logged_user()
        if not user or user.id == user_id:
            return redirect(request.referrer or url_for("gaming"))
        row = GamerFollow.query.filter_by(follower_id=user.id, followed_id=user_id).first()
        if row: db.session.delete(row)
        else: db.session.add(GamerFollow(follower_id=user.id, followed_id=user_id))
        db.session.commit()
        return redirect(request.referrer or url_for("gaming"))

    @app.post("/gaming/friend/<int:user_id>")
    def gaming_friend(user_id):
        user = logged_user()
        if not user or user.id == user_id: return redirect(request.referrer or url_for("gaming"))
        row = GamerFriend.query.filter_by(requester_id=user.id, addressee_id=user_id).first()
        reverse = GamerFriend.query.filter_by(requester_id=user_id, addressee_id=user.id).first()
        if reverse and reverse.status == "pending":
            reverse.status = "accepted"
        elif not row:
            db.session.add(GamerFriend(requester_id=user.id, addressee_id=user_id))
        db.session.commit()
        return redirect(request.referrer or url_for("gaming"))

    @app.post("/gaming/team/create")
    def gaming_team_create():
        user = logged_user()
        if not user:
            flash("برای ساخت تیم ابتدا وارد حساب کاربری شوید.", "warning")
            return redirect(url_for("login", next="/gaming/teams"))
        name = request.form.get("name", "").strip()
        if not name:
            flash("نام تیم را وارد کنید.", "danger")
            return redirect(url_for("gaming_teams"))
        team = GamingTeam(name=name, tag=request.form.get("tag","").strip(), game=request.form.get("game","").strip(),
            platform=request.form.get("platform","PC").strip(), rank=request.form.get("rank","").strip(),
            city=request.form.get("city","").strip(), description=request.form.get("description","").strip(), owner_id=user.id)
        db.session.add(team)
        db.session.flush()
        db.session.add(GamingTeamMember(team_id=team.id, user_id=user.id, role="captain"))
        db.session.commit()
        flash("تیم ساخته شد؛ حالا می‌توانید اعضا را جذب کنید.", "success")
        return redirect(url_for("gaming_teams"))

    @app.post("/gaming/team/<int:team_id>/join")
    def gaming_team_join(team_id):
        user = logged_user()
        if not user:
            return redirect(url_for("login", next=request.referrer or "/gaming/teams"))
        if not GamingTeamMember.query.filter_by(team_id=team_id, user_id=user.id).first():
            db.session.add(GamingTeamMember(team_id=team_id, user_id=user.id))
            db.session.commit()
            flash("عضویت شما در تیم ثبت شد.", "success")
        return redirect(request.referrer or url_for("gaming_teams"))

    @app.post("/gaming/post/create")
    def gaming_post_create():
        user = logged_user()
        if not user:
            flash("برای انتشار پست ابتدا وارد حساب کاربری شوید.", "warning")
            return redirect(url_for("login", next="/gaming/club"))
        title, body = request.form.get("title","").strip(), request.form.get("body","").strip()
        if not title or not body:
            flash("عنوان و متن پست الزامی است.", "danger")
            return redirect(url_for("gaming_club"))
        db.session.add(GamingPost(title=title, body=body, game=request.form.get("game","").strip(),
            post_type=request.form.get("post_type","discussion").strip(), author_id=user.id))
        db.session.commit()
        return redirect(url_for("gaming_club"))

    @app.post("/gaming/post/<int:post_id>/like")
    def gaming_like(post_id):
        user = logged_user()
        if not user: return redirect(url_for("login", next=request.referrer or "/gaming/club"))
        post = db.session.get(GamingPost, post_id)
        if not post: return redirect(request.referrer or url_for("gaming_club"))
        row = GamingLike.query.filter_by(post_id=post_id, user_id=user.id).first()
        if row:
            db.session.delete(row); post.likes_count = max(0, post.likes_count - 1)
        else:
            db.session.add(GamingLike(post_id=post_id, user_id=user.id)); post.likes_count += 1
        db.session.commit()
        return redirect(request.referrer or url_for("gaming_club"))

    @app.post("/gaming/post/<int:post_id>/comment")
    def gaming_comment(post_id):
        user = logged_user()
        body = request.form.get("body","").strip()
        if not user:
            return redirect(url_for("login", next=request.referrer or "/gaming/club"))
        if body:
            db.session.add(GamingComment(post_id=post_id, user_id=user.id, body=body))
            post = db.session.get(GamingPost, post_id)
            if post: post.comments_count += 1
            db.session.commit()
        return redirect(request.referrer or url_for("gaming_club"))

    @app.post("/gaming/matchmaking/create")
    def gaming_matchmaking_create():
        user = logged_user()
        if not user:
            return redirect(url_for("login", next="/gaming/matchmaking"))
        game = request.form.get("game","").strip()[:160]
        if not game:
            flash("انتخاب بازی الزامی است.", "danger")
            return redirect(url_for("gaming_matchmaking"))
        try:
            party_size = max(1, min(10, int(request.form.get("party_size", 1) or 1)))
        except (TypeError, ValueError):
            party_size = 1
        db.session.add(MatchmakingRequest(
            user_id=user.id, game=game, platform=request.form.get("platform","PC").strip()[:40],
            rank=request.form.get("rank","").strip()[:80], mode=request.form.get("mode","Squad").strip()[:80],
            language=request.form.get("language","فارسی").strip()[:80], play_time=request.form.get("play_time","").strip()[:120],
            party_size=party_size,
            mic_required=request.form.get("mic_required") == "on", city=request.form.get("city","").strip()[:80]
        ))
        db.session.commit()
        flash("درخواست هم‌تیمی شما فعال شد.", "success")
        return redirect(url_for("gaming_matchmaking"))

    @app.post("/gaming/tournament/<int:tournament_id>/join")
    def gaming_tournament_join(tournament_id):
        user = logged_user()
        if not user:
            return redirect(url_for("login", next="/gaming/tournaments"))
        t = db.session.get(GamingTournament, tournament_id)
        if t and t.status == "ثبت‌نام باز" and t.participants_count < t.max_players:
            if not TournamentParticipant.query.filter_by(tournament_id=t.id, user_id=user.id).first():
                db.session.add(TournamentParticipant(tournament_id=t.id, user_id=user.id))
                t.participants_count += 1
                db.session.commit()
                flash("ثبت‌نام شما در مسابقه انجام شد.", "success")
        return redirect(url_for("gaming_tournaments"))

    @app.post("/gaming/report")
    def gaming_report():
        user = logged_user()
        if not user: return redirect(url_for("login", next=request.referrer or "/gaming"))
        target_type = request.form.get("target_type","content").strip()[:40]
        try:
            target_id = int(request.form.get("target_id", 0) or 0)
        except (TypeError, ValueError):
            target_id = 0
        reason = request.form.get("reason","").strip()[:120]
        if target_id and reason:
            db.session.add(GamingReport(reporter_id=user.id, target_type=target_type, target_id=target_id, reason=reason,
                                        details=request.form.get("details","").strip()))
            db.session.commit()
            flash("گزارش شما برای بررسی تیم مدیریت ثبت شد.", "success")
        return redirect(request.referrer or url_for("gaming"))

    def _ensure_gaming_schema():
        # Lightweight SQLite migration for existing Kharidino databases.
        # db.create_all() creates new tables but does not add columns to old gaming tables.
        tables = {
            "gaming_game": {
                "cover": "VARCHAR(500)", "publisher": "VARCHAR(160)", "release_year": "INTEGER DEFAULT 2026"
            },
            "gaming_profile": {},
            "gaming_team": {
                "verified": "BOOLEAN DEFAULT 0", "wins": "INTEGER DEFAULT 0", "reputation": "INTEGER DEFAULT 100"
            },
            "gaming_post": {
                "likes_count": "INTEGER DEFAULT 0", "comments_count": "INTEGER DEFAULT 0"
            },
            "gaming_tournament": {
                "max_players": "INTEGER DEFAULT 32", "participants_count": "INTEGER DEFAULT 0"
            }
        }
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        for table, columns in tables.items():
            if not inspector.has_table(table):
                continue
            existing = {x["name"] for x in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    db.session.execute(db.text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}'))
        db.session.commit()

    def seed_gaming():
        _ensure_gaming_schema()
        if GamingQuest.query.count() == 0:
            db.session.add_all([
                GamingQuest(title="اولین پست کلاب", description="یک پست باکیفیت منتشر کن.", xp=120, reward_points=20, kind="weekly"),
                GamingQuest(title="اولین هم‌تیمی", description="یک درخواست Matchmaking بساز.", xp=150, reward_points=25, kind="weekly"),
                GamingQuest(title="ساخت تیم", description="یک تیم یا کلن بساز.", xp=250, reward_points=40, kind="seasonal"),
                GamingQuest(title="رقابت", description="در یک تورنمنت ثبت‌نام کن.", xp=300, reward_points=60, kind="seasonal")
            ])
        if GamingSeason.query.count() == 0:
            season=GamingSeason(name="Kharidino Season 1", active=True); db.session.add(season); db.session.flush()
            db.session.add_all([
                GamingLeague(season_id=season.id,name="Open League",game="Counter-Strike 2",platform="PC",tier="Open",prize="جایزه ویژه"),
                GamingLeague(season_id=season.id,name="FC Champions",game="EA Sports FC 26",platform="PlayStation",tier="Gold",prize="جایزه ویژه")
            ])

        games = [
            ("Counter-Strike 2","counter-strike-2","PC","FPS","Ranked"),
            ("Valorant","valorant","PC","FPS","Ranked"),
            ("EA Sports FC 26","ea-sports-fc-26","PC","Sports","Online"),
            ("Call of Duty Warzone","call-of-duty-warzone","PC","FPS","Battle Royale"),
            ("Fortnite","fortnite","PC","Battle Royale","Squad"),
            ("Minecraft","minecraft","PC","Sandbox","Co-op"),
            ("Grand Theft Auto V","grand-theft-auto-v","PC","Action","Online"),
            ("Apex Legends","apex-legends","PC","FPS","Battle Royale"),
            ("Rocket League","rocket-league","PC","Sports","Online"),
            ("PUBG","pubg","PC","Battle Royale","Squad"),
            ("EA Sports FC 26","ea-sports-fc-26-ps5","PlayStation","Sports","Online"),
            ("Forza Horizon 5","forza-horizon-5","Xbox","Racing","Online"),
        ]
        for name, slug, platform, genre, mode in games:
            if not GamingGame.query.filter_by(name=name, platform=platform).first():
                db.session.add(GamingGame(name=name, slug=slug, platform=platform, genre=genre, mode=mode,
                    description=f"هاب اختصاصی {name}: بازی، جامعه، تیم، هم‌تیمی، مسابقات و محتوای گیمرها."))
        if GamingTeam.query.count() == 0:
            for n,tag,g,p,r,c in [
                ("Kharidino Wolves","KW","Counter-Strike 2","PC","Global","تهران"),
                ("Night Raiders","NR","Valorant","PC","Ascendant","مشهد"),
                ("Persian Legends","PL","EA Sports FC 26","PlayStation","Elite","شیراز"),
                ("Desert Foxes","DF","Call of Duty Warzone","PC","Diamond","تبریز"),
                ("Tehran Titans","TT","Apex Legends","PC","Master","تهران"),
                ("Mashhad Storm","MS","Fortnite","PC","Champion","مشهد"),
                ("Shiraz Phoenix","SP","Rocket League","PC","Grand Champion","شیراز"),
                ("Caspian Guardians","CG","PUBG","PC","Conqueror","رشت"),
            ]:
                db.session.add(GamingTeam(name=n,tag=tag,game=g,platform=p,rank=r,city=c,description="تیم رقابتی کلاب خریدینو",wins=10,reputation=120))
        if GamingTournament.query.count() == 0:
            for x in [
                ("Kharidino Gaming Cup","Counter-Strike 2","PC","جایزه ویژه","ثبت‌نام باز","۱۴۰۵/۰۸/۲۰",64),
                ("Kharidino FC Challenge","EA Sports FC 26","PlayStation","جوایز نقدی","ثبت‌نام باز","۱۴۰۵/۰۸/۲۷",32),
                ("Valorant Night","Valorant","PC","جوایز تیمی","به‌زودی","۱۴۰۵/۰۹/۰۵",32),
            ]:
                db.session.add(GamingTournament(title=x[0],game=x[1],platform=x[2],prize=x[3],status=x[4],date_text=x[5],max_players=x[6]))
        # Demo gaming roster: safe, non-login seed accounts for a lively showcase.
        player_specs = [
            ("Arman","Arman_Wolf","Counter-Strike 2","PC","Global Elite","⚔️ AWP Phantom","Legendary"),
            ("Nima","NimaRush","Valorant","PC","Immortal 3","🎯 Neon Aim","Epic"),
            ("Sina","SinaKing","EA Sports FC 26","PlayStation","Elite","👑 Golden Striker","Legendary"),
            ("Pouya","PouyaX","Call of Duty Warzone","PC","Crimson","🪖 Warzone Loadout","Epic"),
            ("Reza","RezaDrive","Forza Horizon 5","Xbox","S2 Elite","🏎️ Turbo Falcon","Rare"),
            ("Amir","AmirBuilds","Minecraft","PC","Builder","⛏️ Nether Pickaxe","Epic"),
            ("Milad","MiladRocket","Rocket League","PC","Champion","🚀 Rocket Boost","Rare"),
            ("Navid","NavidPUBG","PUBG","PC","Ace Master","🛡️ Chicken Dinner Badge","Legendary"),
        ]
        for name,tag,game,platform,rank,item_name,rarity in player_specs:
            email=f"gaming.demo.{tag.lower()}@example.invalid"
            user=User.query.filter_by(email=email).first()
            if not user:
                user=User(name=name,email=email,password=generate_password_hash("demo-only-disabled"),role="user")
                db.session.add(user); db.session.flush()
            profile=GamerProfile.query.filter_by(user_id=user.id).first()
            if not profile:
                profile=GamerProfile(user_id=user.id,gamer_tag=tag,platform=platform,level=20,xp=9500,reputation=150,status="online",favorite_games=game)
                db.session.add(profile); db.session.flush()
            if not GamingGameStat.query.filter_by(user_id=user.id,game=game,platform=platform).first():
                db.session.add(GamingGameStat(user_id=user.id,game=game,platform=platform,rank=rank,wins=42,losses=12,hours=320,mmr=1800))
            if not GamingPlayerItem.query.filter_by(user_id=user.id).first():
                db.session.add(GamingPlayerItem(user_id=user.id,name=item_name,rarity=rarity,description=f"آیتم نمایشی اختصاصی {tag}",equipped=True))
        db.session.flush()
        seeded_players=GamerProfile.query.filter(GamerProfile.gamer_tag.in_([x[1] for x in player_specs])).all()
        seeded_teams=GamingTeam.query.order_by(GamingTeam.id.asc()).limit(8).all()
        for idx, profile in enumerate(seeded_players):
            team=seeded_teams[idx % len(seeded_teams)] if seeded_teams else None
            if team and not GamingTeamMember.query.filter_by(team_id=team.id,user_id=profile.user_id).first():
                db.session.add(GamingTeamMember(team_id=team.id,user_id=profile.user_id,role="member"))
        if GamingPost.query.count() == 0:
            for x in [
                ("بهترین تنظیمات FPS برای سیستم متوسط","تنظیمات بهینه برای فریم پایدار و رقابتی.","Counter-Strike 2","guide"),
                ("هم‌تیمی برای رنک","برای یک تیم ۵ نفره بازیکن رنک‌دار می‌خواهیم.","Valorant","looking"),
                ("Setup خودتو معرفی کن","عکس و مشخصات ستاپ گیمینگ خودت را در کلاب منتشر کن.","","setup"),
            ]:
                db.session.add(GamingPost(title=x[0],body=x[1],game=x[2],post_type=x[3]))
        db.session.commit()

    app._kharidino_gaming_registered = True
    app._kharidino_gaming_seed = seed_gaming
    return seed_gaming
