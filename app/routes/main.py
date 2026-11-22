from flask import Blueprint, render_template, request, abort, redirect, url_for
from app.models import KnowledgeArticle, TicketCategory, Ticket, User
from app.decorators import get_current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # If already logged in, show personalized banner or redirect to respective dashboard
    user = get_current_user()
    
    # Recent published articles
    featured_articles = KnowledgeArticle.query.filter_by(is_published=True).order_by(KnowledgeArticle.views_count.desc()).limit(6).all()
    categories = TicketCategory.query.filter_by(is_active=True).all()
    
    # Real metrics from SQLite
    total_tickets = Ticket.query.count()
    resolved_tickets = Ticket.query.filter(Ticket.status.in_(['Resolved', 'Closed'])).count()
    total_articles = KnowledgeArticle.query.filter_by(is_published=True).count()
    
    return render_template(
        'index.html',
        featured_articles=featured_articles,
        categories=categories,
        total_tickets=total_tickets,
        resolved_tickets=resolved_tickets,
        total_articles=total_articles,
        user=user
    )

@main_bp.route('/kb')
def kb_index():
    query = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)

    articles_query = KnowledgeArticle.query.filter_by(is_published=True)

    if query:
        articles_query = articles_query.filter(
            (KnowledgeArticle.title.ilike(f'%{query}%')) | 
            (KnowledgeArticle.content.ilike(f'%{query}%'))
        )

    if category_id:
        articles_query = articles_query.filter_by(category_id=category_id)

    articles = articles_query.order_by(KnowledgeArticle.views_count.desc()).all()
    categories = TicketCategory.query.filter_by(is_active=True).all()

    return render_template(
        'kb/index.html',
        articles=articles,
        categories=categories,
        search_query=query,
        selected_category_id=category_id
    )

@main_bp.route('/kb/<slug>')
def kb_article(slug):
    article = KnowledgeArticle.query.filter_by(slug=slug, is_published=True).first_or_404()
    
    # Increment view count
    article.views_count += 1
    from app.extensions import db
    db.session.commit()

    related_articles = KnowledgeArticle.query.filter(
        KnowledgeArticle.id != article.id,
        KnowledgeArticle.category_id == article.category_id,
        KnowledgeArticle.is_published == True
    ).limit(4).all()

    return render_template(
        'kb/article.html',
        article=article,
        related_articles=related_articles
    )
