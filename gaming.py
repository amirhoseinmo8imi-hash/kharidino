from flask import render_template, request, session, redirect, url_for, flash
from datetime import datetime

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
        active = db.Column(db.Boolean, default=True)

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
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class GamingPost(db.Model):
        __tablename__ = "gaming_post"
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(180), nullable=False)
        body = db.Column(db.Text, default="")
        game = db.Column(db.String(120), default="")
        post_type = db.Column(db.String(40), default="discussion")
        author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
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

    app.jinja_env.globals["gaming_game_model"] = GamingGame

    def catalog():
        q = request.args.get("q","").strip()
        platform = request.args.get("platform","").strip()
        genre = request.args.get("genre","").strip()
        mode = request.args.get("mode","").strip()
        sort = request.args.get("sort","popular").strip()
        query = GamingGame.query.filter_by(active=True)
        if q:
            like = f"%{q}%"
            query = query.filter(db.or_(GamingGame.name.ilike(like), GamingGame.description.ilike(like)))
        if platform:
            query = query.filter_by(platform=platform)
        if genre:
            query = query.filter_by(genre=genre)
        if mode:
            query = query.filter_by(mode=mode)
        games = query.order_by(GamingGame.name.asc() if sort == "name" else GamingGame.id.desc()).all()
        teams = GamingTeam.query.order_by(GamingTeam.id.desc()).limit(8).all()
        tournaments = GamingTournament.query.order_by(GamingTournament.id.desc()).limit(6).all()
        posts = GamingPost.query.order_by(GamingPost.id.desc()).limit(8).all()
        return render_template("gaming/index.html", games=games, teams=teams, tournaments=tournaments, posts=posts,
                               q=q, platform=platform, genre=genre, mode=mode, sort=sort)

    app.add_url_rule("/gaming", "gaming", catalog)

    @app.get("/gaming/club")
    def gaming_club():
        teams = GamingTeam.query.order_by(GamingTeam.id.desc()).all()
        posts = GamingPost.query.order_by(GamingPost.id.desc()).all()
        tournaments = GamingTournament.query.order_by(GamingTournament.id.desc()).all()
        return render_template("gaming/club.html", teams=teams, posts=posts, tournaments=tournaments)

    @app.get("/gaming/teams")
    def gaming_teams():
        game = request.args.get("game","").strip()
        platform = request.args.get("platform","").strip()
        rank = request.args.get("rank","").strip()
        city = request.args.get("city","").strip()
        query = GamingTeam.query
        if game: query = query.filter_by(game=game)
        if platform: query = query.filter_by(platform=platform)
        if rank: query = query.filter_by(rank=rank)
        if city: query = query.filter_by(city=city)
        return render_template("gaming/teams.html", teams=query.order_by(GamingTeam.id.desc()).all(),
                               game=game, platform=platform, rank=rank, city=city)

    @app.get("/gaming/matchmaking")
    def gaming_matchmaking():
        games = GamingGame.query.filter_by(active=True).order_by(GamingGame.name).all()
        return render_template("gaming/matchmaking.html", games=games)

    @app.get("/gaming/tournaments")
    def gaming_tournaments():
        return render_template("gaming/tournaments.html", tournaments=GamingTournament.query.order_by(GamingTournament.id.desc()).all())

    @app.get("/gaming/game/<slug>")
    def gaming_game(slug):
        game = GamingGame.query.filter_by(slug=slug, active=True).first_or_404()
        related = GamingGame.query.filter(GamingGame.id != game.id, GamingGame.platform == game.platform).limit(6).all()
        teams = GamingTeam.query.filter_by(game=game.name).limit(12).all()
        return render_template("gaming/game.html", game=game, related=related, teams=teams)

    @app.post("/gaming/team/create")
    def gaming_team_create():
        user_id = session.get("user_id")
        if not user_id:
            flash("برای ساخت تیم ابتدا وارد حساب کاربری شوید.", "warning")
            return redirect(url_for("login", next="/gaming/club"))
        name = request.form.get("name","").strip()
        if not name:
            flash("نام تیم را وارد کنید.", "danger")
            return redirect(url_for("gaming_teams"))
        db.session.add(GamingTeam(name=name, tag=request.form.get("tag","").strip(),
            game=request.form.get("game","").strip(), platform=request.form.get("platform","PC").strip(),
            rank=request.form.get("rank","").strip(), city=request.form.get("city","").strip(),
            description=request.form.get("description","").strip(), owner_id=user_id))
        db.session.commit()
        flash("تیم با موفقیت در کلاب ساخته شد.", "success")
        return redirect(url_for("gaming_teams"))

    @app.post("/gaming/post/create")
    def gaming_post_create():
        user_id = session.get("user_id")
        if not user_id:
            flash("برای انتشار پست ابتدا وارد حساب کاربری شوید.", "warning")
            return redirect(url_for("login", next="/gaming/club"))
        title = request.form.get("title","").strip()
        body = request.form.get("body","").strip()
        if not title or not body:
            flash("عنوان و متن پست الزامی است.", "danger")
            return redirect(url_for("gaming_club"))
        db.session.add(GamingPost(title=title, body=body, game=request.form.get("game","").strip(),
            post_type=request.form.get("post_type","discussion").strip(), author_id=user_id))
        db.session.commit()
        flash("پست شما در کلاب منتشر شد.", "success")
        return redirect(url_for("gaming_club"))

    def seed_gaming():
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
                                          description=f"جامعه گیمرها، تیم‌ها و محتوای {name} در کلاب خریدینو."))
        if GamingTeam.query.count() == 0:
            for n,tag,g,p,r,c in [
                ("Kharidino Wolves","KW","Counter-Strike 2","PC","Global","تهران"),
                ("Night Raiders","NR","Valorant","PC","Ascendant","مشهد"),
                ("Persian Legends","PL","EA Sports FC 26","PlayStation","Elite","شیراز"),
                ("Desert Foxes","DF","Call of Duty Warzone","PC","Diamond","تبریز"),
            ]:
                db.session.add(GamingTeam(name=n,tag=tag,game=g,platform=p,rank=r,city=c,description="تیم فعال کلاب خریدینو"))
        if GamingTournament.query.count() == 0:
            for x in [
                ("Kharidino Gaming Cup","Counter-Strike 2","PC","جایزه ویژه","ثبت‌نام باز","۱۴۰۵/۰۸/۲۰"),
                ("Kharidino FC Challenge","EA Sports FC 26","PlayStation","جوایز نقدی","ثبت‌نام باز","۱۴۰۵/۰۸/۲۷"),
                ("Valorant Night","Valorant","PC","جوایز تیمی","به‌زودی","۱۴۰۵/۰۹/۰۵"),
            ]:
                db.session.add(GamingTournament(title=x[0],game=x[1],platform=x[2],prize=x[3],status=x[4],date_text=x[5]))
        if GamingPost.query.count() == 0:
            for x in [
                ("بهترین تنظیمات FPS برای سیستم متوسط","FPS را با تنظیمات مناسب و پایدار بازی کنید.","Counter-Strike 2","guide"),
                ("هم‌تیمی برای رنک","برای یک تیم ۵ نفره بازیکن رنک‌دار می‌خواهیم.","Valorant","looking"),
                ("Setup خودتو معرفی کن","عکس و مشخصات ستاپ گیمینگ خودت را در کلاب منتشر کن.","","setup"),
            ]:
                db.session.add(GamingPost(title=x[0],body=x[1],game=x[2],post_type=x[3]))
        db.session.commit()

    return seed_gaming
