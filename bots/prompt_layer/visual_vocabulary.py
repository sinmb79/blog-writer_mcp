"""
bots/prompt_layer/visual_vocabulary.py
Shared Korean -> English visual concept dictionary.
Used by search_query.py and video_prompt.py for concept mapping.
"""

CONCEPT_TO_VISUAL = {
    # Technology
    'AI': ['artificial intelligence screen', 'digital interface', 'neural network visualization'],
    '인공지능': ['robot brain', 'digital mind', 'AI hologram'],
    '자동화': ['gears mechanism', 'conveyor belt', 'robot arm factory'],
    '코딩': ['computer code screen', 'programmer keyboard', 'dark terminal code'],
    '데이터': ['data visualization', 'bar chart analytics', 'network nodes'],
    '알고리즘': ['flowchart diagram', 'binary code', 'decision tree'],
    '앱': ['smartphone screen', 'mobile app interface', 'app store'],
    '소프트웨어': ['software development', 'code editor', 'programming laptop'],
    # Finance/Money
    '돈': ['money cash bills', 'coins pile', 'dollar bills'],
    '수익': ['profit growth chart', 'rising arrow money', 'income cash'],
    '투자': ['stock market chart', 'investment portfolio', 'financial growth'],
    '절약': ['piggy bank savings', 'money jar coins', 'budget planning'],
    '부자': ['luxury lifestyle', 'wealthy business person', 'success achievement'],
    '무료': ['gift present box', 'unlocked padlock', 'free tag label'],
    '할인': ['sale discount tag', 'percent off sign', 'price reduction'],
    # Business
    '비즈니스': ['business meeting', 'office workspace', 'professional handshake'],
    '창업': ['startup launch rocket', 'entrepreneur office', 'business idea lightbulb'],
    '마케팅': ['marketing strategy board', 'social media icons', 'advertising billboard'],
    '브랜드': ['brand logo design', 'brand identity', 'premium label'],
    '고객': ['customer service smile', 'client meeting', 'happy customer'],
    '성공': ['success achievement trophy', 'winner podium', 'goal celebration'],
    '실패': ['failure mistake frustrated', 'broken plan', 'problem obstacle'],
    # Health/Lifestyle
    '건강': ['healthy lifestyle', 'fitness exercise', 'fresh vegetables'],
    '다이어트': ['diet food salad', 'weight loss scale', 'healthy eating'],
    '운동': ['gym workout exercise', 'running sport', 'fitness training'],
    '수면': ['peaceful sleep bedroom', 'sleeping person night', 'rest relaxation'],
    '스트레스': ['stress anxiety person', 'overwhelmed work', 'headache pressure'],
    '행복': ['happy smiling person', 'joy celebration', 'positive energy'],
    # Education
    '공부': ['studying books desk', 'student learning', 'open textbook'],
    '독서': ['reading book cozy', 'bookshelf library', 'person reading'],
    '교육': ['classroom teaching', 'education school', 'learning knowledge'],
    '자격증': ['certificate diploma award', 'achievement credential', 'professional certification'],
    # Social/Communication
    '소통': ['communication talking', 'conversation speech bubble', 'people talking'],
    '관계': ['relationship people together', 'friendship bond', 'social connection'],
    '가족': ['family together happy', 'family portrait', 'home family'],
    '친구': ['friends together laughing', 'friendship bond', 'social gathering'],
    # Environment/Nature
    '자연': ['nature landscape scenic', 'green forest trees', 'outdoor beauty'],
    '환경': ['environment ecology', 'green earth planet', 'sustainability'],
    '도시': ['city skyline urban', 'modern architecture', 'downtown cityscape'],
    '여행': ['travel adventure journey', 'wanderlust explore', 'tourism destination'],
    # Time/Productivity
    '시간': ['clock time management', 'hourglass countdown', 'calendar schedule'],
    '생산성': ['productivity work desk', 'efficient workflow', 'organized workspace'],
    '습관': ['habit routine daily', 'calendar habit tracker', 'consistent practice'],
    '목표': ['goal target arrow', 'achievement milestone', 'success roadmap'],
    # Food
    '음식': ['food meal delicious', 'restaurant dining', 'cooking kitchen'],
    '커피': ['coffee cup cafe', 'espresso morning', 'coffee shop cozy'],
    '요리': ['cooking chef kitchen', 'recipe preparation', 'homemade food'],
    # Digital/Social Media
    '유튜브': ['youtube play button', 'video content creator', 'streaming platform'],
    '틱톡': ['social media video', 'short video content', 'viral content'],
    '인스타그램': ['instagram photo aesthetic', 'social media post', 'influencer lifestyle'],
    '콘텐츠': ['content creation studio', 'digital content', 'creative media'],
    # Generic actions
    '시작': ['starting launch beginning', 'new start fresh', 'launch rocket'],
    '변화': ['change transformation', 'before after contrast', 'evolution progress'],
    '성장': ['growth plant sprouting', 'growth chart rising', 'development progress'],
    '문제': ['problem solving puzzle', 'challenge obstacle', 'issue question mark'],
    '해결': ['solution lightbulb', 'problem solved checkmark', 'resolution answer'],
    '비교': ['comparison side by side', 'versus contrast', 'pros cons balance'],
    '순위': ['ranking top list', 'leaderboard winners', 'chart comparison'],
    '방법': ['how-to guide steps', 'tutorial instruction', 'method process'],
    '팁': ['tips tricks advice', 'helpful hints', 'pro tip star'],
    '비밀': ['secret reveal hidden', 'mystery unlock', 'insider knowledge'],
    '진실': ['truth reveal facts', 'reality check', 'honest disclosure'],
    '놀라운': ['surprising amazing wow', 'unexpected revelation', 'shocking discovery'],
    # Numbers/Stats
    '1위': ['number one winner', 'first place gold', 'top ranked best'],
    '100%': ['one hundred percent complete', 'full capacity', 'perfect score'],
    # Korean culture
    '한국': ['korea seoul cityscape', 'korean culture', 'hanbok traditional'],
    '직장': ['office workplace corporate', 'work desk professional', 'business office'],
    '취업': ['job interview hiring', 'employment opportunity', 'career success'],
    '부동산': ['real estate property', 'house home investment', 'property market'],
    # Abstract concepts
    '가능성': ['possibility open door', 'opportunity horizon', 'potential unlimited'],
    '미래': ['future technology vision', 'futuristic landscape', 'innovation tomorrow'],
    '트렌드': ['trend arrow upward', 'trending popular', 'hot topic social'],
}

# Quality/style modifiers to append to video/image prompts
VISUAL_STYLE_MODIFIERS = [
    'cinematic',
    '4k',
    'professional',
    'high quality',
    'vibrant colors',
    'sharp focus',
    'natural lighting',
    'smooth motion',
]

# Terms to avoid in video generation prompts
NEGATIVE_TERMS = [
    'blurry',
    'low quality',
    'watermark',
    'text overlay',
    'distorted',
    'pixelated',
    'grainy',
    'overexposed',
    'underexposed',
    'shaky camera',
]


if __name__ == '__main__':
    import sys

    if '--test' in sys.argv:
        print('=== visual_vocabulary 테스트 시작 ===')
        print(f'총 개념 수: {len(CONCEPT_TO_VISUAL)}')
        print(f'스타일 수식어 수: {len(VISUAL_STYLE_MODIFIERS)}')
        print(f'네거티브 용어 수: {len(NEGATIVE_TERMS)}')
        print()

        # Test a few lookups
        test_concepts = ['AI', '미래', '성공', '건강', '코딩']
        for concept in test_concepts:
            visuals = CONCEPT_TO_VISUAL.get(concept, [])
            print(f'  [{concept}] -> {visuals}')

        print()
        print(f'스타일 수식어: {VISUAL_STYLE_MODIFIERS}')
        print(f'네거티브 용어: {NEGATIVE_TERMS}')
        print()
        print('=== 테스트 완료 ===')
    else:
        print('사용법: python -m bots.prompt_layer.visual_vocabulary --test')
