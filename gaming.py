from datetime import datetime
from flask import render_template, request, session, redirect, url_for, flash
from sqlalchemy import or_, func

def register_gaming(app, db, User):
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
        teams = GamingTeamMember.query.filter_by(user_id=profile.user_id).all()
        is_following = bool(logged_user() and GamerFollow.query.filter_by(follower_id=logged_user().id, followed_id=profile.user_id).first())
        return render_template("gaming/profile.html", profile=profile, stats=stats, achievements=achievements,
                               followers=followers, following=following, teams=teams, is_following=is_following)

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
        p.gamer_tag = request.form.get("gamer_tag", p.gamer_tag).strip()[:80] or p.gamer_tag
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
        db.session.add(MatchmakingRequest(
            user_id=user.id, game=request.form.get("game","").strip(), platform=request.form.get("platform","PC").strip(),
            rank=request.form.get("rank","").strip(), mode=request.form.get("mode","Squad").strip(),
            language=request.form.get("language","فارسی").strip(), play_time=request.form.get("play_time","").strip(),
            party_size=max(1, int(request.form.get("party_size",1) or 1)),
            mic_required=request.form.get("mic_required") == "on", city=request.form.get("city","").strip()
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
        target_type = request.form.get("target_type","content").strip()
        target_id = int(request.form.get("target_id",0) or 0)
        reason = request.form.get("reason","").strip()
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
        _ensure_gaming_schema()\n        games = [
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
            ]:
                db.session.add(GamingTeam(name=n,tag=tag,game=g,platform=p,rank=r,city=c,description="تیم رقابتی کلاب خریدینو",wins=10,reputation=120))
        if GamingTournament.query.count() == 0:
            for x in [
                ("Kharidino Gaming Cup","Counter-Strike 2","PC","جایزه ویژه","ثبت‌نام باز","۱۴۰۵/۰۸/۲۰",64),
                ("Kharidino FC Challenge","EA Sports FC 26","PlayStation","جوایز نقدی","ثبت‌نام باز","۱۴۰۵/۰۸/۲۷",32),
                ("Valorant Night","Valorant","PC","جوایز تیمی","به‌زودی","۱۴۰۵/۰۹/۰۵",32),
            ]:
                db.session.add(GamingTournament(title=x[0],game=x[1],platform=x[2],prize=x[3],status=x[4],date_text=x[5],max_players=x[6]))
        if GamingPost.query.count() == 0:
            for x in [
                ("بهترین تنظیمات FPS برای سیستم متوسط","تنظیمات بهینه برای فریم پایدار و رقابتی.","Counter-Strike 2","guide"),
                ("هم‌تیمی برای رنک","برای یک تیم ۵ نفره بازیکن رنک‌دار می‌خواهیم.","Valorant","looking"),
                ("Setup خودتو معرفی کن","عکس و مشخصات ستاپ گیمینگ خودت را در کلاب منتشر کن.","","setup"),
            ]:
                db.session.add(GamingPost(title=x[0],body=x[1],game=x[2],post_type=x[3]))
        db.session.commit()

    return seed_gaming
