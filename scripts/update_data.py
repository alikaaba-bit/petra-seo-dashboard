#!/usr/bin/env python3
"""Tracked keyword configuration and backwards-compatible v2 entry point."""
# Historical configuration only: not an endorsement or an active acquisition list.
# Keep this reference and existing data/history files when reviewing past reports.
HISTORICAL_TARGET_KEYWORDS = {
    'china_location': [
        'jewelry manufacturer china', 'china jewelry factory',
        'stainless steel jewelry manufacturer china', 'jewelry supplier china wholesale',
        'premium jewelry manufacturer china', 'jewelry factory dongguan',
        'chinese jewelry manufacturer for brands', 'china jewelry factory high quality',
        'silver jewelry manufacturer china', 'brass jewelry manufacturer china',
    ],
    'durability': [
        'hard jewelry manufacturer', 'durable jewelry manufacturer', 'waterproof jewelry manufacturer',
        'tarnish free jewelry supplier', 'lifetime warranty jewelry manufacturer',
        'hypoallergenic jewelry manufacturer', 'long lasting jewelry supplier', 'surgical steel jewelry manufacturer',
    ],
    'materials': [
        'stainless steel jewelry manufacturer', '316L stainless steel jewelry supplier',
        'brass jewelry manufacturer', 'sterling silver jewelry manufacturer', '925 silver jewelry wholesale',
        'PVD plated jewelry manufacturer', 'gold plated stainless steel jewelry wholesale',
        'rose gold jewelry manufacturer', 'stainless steel jewelry factory', 'nickel free jewelry manufacturer',
    ],
    'private_label': [
        'private label jewelry manufacturer', 'OEM jewelry manufacturer', 'ODM jewelry manufacturer',
        'white label jewelry manufacturer', 'custom jewelry manufacturer',
        'private label jewelry manufacturer china', 'contract jewelry manufacturer', 'jewelry manufacturing partner',
    ],
    'ecommerce': [
        'jewelry manufacturer for ecommerce brands', 'jewelry supplier for DTC brands',
        'jewelry manufacturer for shopify brands', 'wholesale jewelry supplier for online stores',
        'B2B jewelry manufacturer', 'jewelry manufacturer for retailers', 'jewelry supplier for amazon sellers',
    ],
    'quality': [
        'premium jewelry manufacturer', 'high quality jewelry factory', 'reliable jewelry manufacturer',
        'jewelry manufacturer quality control', 'best jewelry manufacturer for brands',
        'luxury stainless steel jewelry manufacturer', 'consistent jewelry manufacturing supplier',
    ],
}
TARGET_REVIEWED_AT = '2026-11-17'
TARGET_KEYWORDS = {
    'stainless_steel': [
        'stainless steel jewelry manufacturer', 'custom stainless steel jewelry manufacturer',
        'stainless steel jewellery manufacturer', 'stainless steel jewelry OEM manufacturer',
    ],
    'manufacturing_models': [
        'private label jewelry manufacturer', 'custom jewelry manufacturer for brands',
        'OEM jewelry manufacturer',
    ],
    'product_manufacturing': [
        'stainless steel ring manufacturer', 'stainless steel necklace manufacturer',
        'stainless steel earrings manufacturer',
    ],
    'buyer_preparation': [
        'jewelry manufacturing brief template', 'jewelry manufacturing sample approval checklist',
        'jewelry supplier evaluation checklist',
    ],
    'silver_secondary': ['silver jewelry manufacturer'],
}
# Spelling and OEM variants share an intended destination; they are not extra pages.
# Claim-led, brand-navigation and unselected legacy terms remain historical only.
ALL_KEYWORDS = [keyword for keywords in TARGET_KEYWORDS.values() for keyword in keywords]
HISTORICAL_KEYWORDS = [keyword for keywords in HISTORICAL_TARGET_KEYWORDS.values() for keyword in keywords]
HIGH_PRIORITY = ['stainless steel jewelry manufacturer', 'custom stainless steel jewelry manufacturer',
                 'private label jewelry manufacturer', 'custom jewelry manufacturer for brands',
                 'OEM jewelry manufacturer', 'jewelry manufacturing brief template']
# Proposed destinations from the dated keyword review, not approved or published routes.
TARGET_PAGES = {
    **{keyword: '/stainless-steel-jewelry-manufacturer/' for keyword in TARGET_KEYWORDS['stainless_steel']},
    'private label jewelry manufacturer': '/private-label/',
    'custom jewelry manufacturer for brands': '/contract-manufacturing/',
    'OEM jewelry manufacturer': '/contract-manufacturing/',
    'stainless steel ring manufacturer': '/stainless-steel-jewelry-manufacturer/rings/',
    'stainless steel necklace manufacturer': '/stainless-steel-jewelry-manufacturer/necklaces-pendants/',
    'stainless steel earrings manufacturer': '/stainless-steel-jewelry-manufacturer/earrings/',
    'jewelry manufacturing brief template': '/resources/jewelry-manufacturing-brief/',
    'jewelry manufacturing sample approval checklist': '/resources/stainless-steel-sample-approval/',
    'jewelry supplier evaluation checklist': '/how-to-evaluate-jewelry-manufacturing-partners-a-quality-checklist/',
    'silver jewelry manufacturer': '/silver-jewelry-manufacturer/',
}

if __name__ == '__main__':
    from seo_pipeline import main
    main()
