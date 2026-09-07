#!/usr/bin/env python3
"""Tracked keyword configuration and backwards-compatible v2 entry point."""
TARGET_KEYWORDS = {
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
ALL_KEYWORDS = [keyword for keywords in TARGET_KEYWORDS.values() for keyword in keywords]
HIGH_PRIORITY = ['jewelry manufacturer china', 'stainless steel jewelry manufacturer',
                 'private label jewelry manufacturer', 'hard jewelry manufacturer',
                 '316L stainless steel jewelry supplier', 'jewelry manufacturer for ecommerce brands',
                 'premium jewelry manufacturer china']

if __name__ == '__main__':
    from seo_pipeline import main
    main()
