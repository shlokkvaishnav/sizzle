import { useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import BlurText from '../components/BlurText'
import TypewriterText from '../components/TypewriterText'
import {
    motion, ScrollReveal, StaggerReveal, AnimatedNumber,
    fadeInUp, fadeInLeft, fadeInRight, staggerContainer, staggerItem,
    staggerContainerSlow, scaleIn, popIn, slideInFromLeft, slideInFromRight
} from '../utils/animations'
import Navbar from '../components/Navbar'
import { useTranslation } from '../context/LanguageContext'
import translations from '../i18n/translations'

const heroImages = [
    '/images/hero1.png',
    '/images/hero2.png',
    '/images/hero3.png',
]

export default function Landing() {
    const navigate = useNavigate()
    const location = useLocation()
    const { t, language } = useTranslation()
    const [activeSlide, setActiveSlide] = useState(0)
    const [fadeClass, setFadeClass] = useState('lp-slide-visible')
    const [titleLoaded, setTitleLoaded] = useState(false)
    const intervalRef = useRef(null)

    // Scroll to hash section when navigating from another page (e.g. /about → /#features)
    useEffect(() => {
        if (location.hash) {
            const id = location.hash.replace('#', '')
            setTimeout(() => {
                const el = document.getElementById(id)
                if (el) el.scrollIntoView({ behavior: 'smooth' })
            }, 100)
        }
    }, [location.hash])
    // Auto-advance slides
    useEffect(() => {
        intervalRef.current = setInterval(() => {
            changeSlide((prev) => (prev + 1) % heroImages.length)
        }, 5000)
        return () => clearInterval(intervalRef.current)
    }, [])

    const changeSlide = (getNext) => {
        setFadeClass('lp-slide-fading')
        setTimeout(() => {
            setActiveSlide((prev) => {
                const next = typeof getNext === 'function' ? getNext(prev) : getNext
                return next
            })
            setFadeClass('lp-slide-visible')
        }, 400)
    }

    const nextSlide = () => {
        clearInterval(intervalRef.current)
        changeSlide((prev) => (prev + 1) % heroImages.length)
    }

    const prevSlide = () => {
        clearInterval(intervalRef.current)
        changeSlide((prev) => (prev - 1 + heroImages.length) % heroImages.length)
    }

    return (
        <div className="lp">
            {/* Shared Navbar */}
            <Navbar />

            {/* Hero */}
            <section className="lp-hero">
                {/* Left content */}
                <div className="lp-hero-left">
                    <BlurText
                        text="SIZZLE"
                        delay={150}
                        animateBy="chars"
                        direction="top"
                        className="lp-hero-title"
                        onAnimationComplete={() => setTitleLoaded(true)}
                    />

                    <div className="lp-hero-tagline">
                        <TypewriterText
                            baseText={t('hero_tagline_base')}
                            words={(translations[language] || translations.en).hero_tagline_words}
                            start={titleLoaded}
                            typeDelay={45}
                            deleteDelay={20}
                            pauseTime={600}
                        />
                    </div>

                    <motion.div
                        className="lp-hero-line"
                        initial={{ width: 0 }}
                        animate={titleLoaded ? { width: 80 } : {}}
                        transition={{ duration: 0.8, delay: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
                    />

                    <motion.p
                        className="lp-hero-desc"
                        initial={{ opacity: 0, y: 20 }}
                        animate={titleLoaded ? { opacity: 1, y: 0 } : {}}
                        transition={{ duration: 0.6, delay: 0.5 }}
                    >
                        {t('hero_desc')}
                    </motion.p>

                    <motion.button
                        className="lp-cta lp-cta-pill"
                        onClick={() => navigate('/login')}
                        initial={{ opacity: 0, y: 20 }}
                        animate={titleLoaded ? { opacity: 1, y: 0 } : {}}
                        transition={{ duration: 0.6, delay: 0.7 }}
                        whileHover={{ scale: 1.04, y: -2 }}
                        whileTap={{ scale: 0.97 }}
                    >
                        {t('hero_cta')}
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></svg>
                    </motion.button>
                </div>

                {/* Right: image with blur/fade overlay */}
                <div className="lp-hero-right">
                    <div className="lp-main-image">
                        <img
                            src={heroImages[activeSlide]}
                            alt="Restaurant food"
                            className={`lp-hero-img ${fadeClass}`}
                        />
                        {/* Gradient fade overlays */}
                        <div className="lp-fade-left" />
                        <div className="lp-fade-bottom" />
                        <div className="lp-fade-top" />
                    </div>
                </div>
            </section>

            {/* Marquee */}
            <section className="lp-marquee-section">
                <p className="lp-marquee-label">{t('hero_marquee')}</p>
                <div className="lp-marquee-track">
                    <div className="lp-marquee-content">
                        {[
                            'Bombay Brasserie',
                            'The Curry Collective',
                            'Tandoor Royale',
                            'Spice Republic',
                            'Naan & Kabab Co.',
                            'The Saffron Table',
                            'Masala Street',
                            'Charcoal Kitchen',
                            'Zest Dining',
                            'The Mughal Room',
                            'Flames & Grill',
                            'Peshawari House',
                        ].map((name, i) => (
                            <span key={i} className="lp-marquee-item">
                                <span className="lp-marquee-name">{name}</span>
                                <span className="lp-marquee-dot" />
                            </span>
                        ))}
                    </div>
                    {/* Duplicate for seamless loop */}
                    <div className="lp-marquee-content" aria-hidden="true">
                        {[
                            'Bombay Brasserie',
                            'The Curry Collective',
                            'Tandoor Royale',
                            'Spice Republic',
                            'Naan & Kabab Co.',
                            'The Saffron Table',
                            'Masala Street',
                            'Charcoal Kitchen',
                            'Zest Dining',
                            'The Mughal Room',
                            'Flames & Grill',
                            'Peshawari House',
                        ].map((name, i) => (
                            <span key={`dup-${i}`} className="lp-marquee-item">
                                <span className="lp-marquee-name">{name}</span>
                                <span className="lp-marquee-dot" />
                            </span>
                        ))}
                    </div>
                </div>
            </section>

            {/* Features Strip */}
            <section className="lp-features" id="features">
                <StaggerReveal className="lp-features-inner" variants={staggerContainerSlow}>
                    {[
                        { num: '01', titleKey: 'feature_1_title', descKey: 'feature_1_desc' },
                        { num: '02', titleKey: 'feature_2_title', descKey: 'feature_2_desc' },
                        { num: '03', titleKey: 'feature_3_title', descKey: 'feature_3_desc' },
                        { num: '04', titleKey: 'feature_4_title', descKey: 'feature_4_desc' },
                    ].map((f, i) => (
                        <motion.div key={i} className="lp-feature-item" variants={staggerItem}
                            whileHover={{ backgroundColor: 'rgba(22, 22, 22, 1)', transition: { duration: 0.3 } }}
                        >
                            <motion.span
                                className="lp-feature-num"
                                initial={{ opacity: 0, x: -10 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: 0.1 * i, duration: 0.4 }}
                            >
                                {f.num}
                            </motion.span>
                            <h3>{t(f.titleKey)}</h3>
                            <p>{t(f.descKey)}</p>
                        </motion.div>
                    ))}
                </StaggerReveal>
            </section>

            {/* About */}
            <section className="lp-about" id="about">
                <div className="lp-about-inner">
                    <ScrollReveal className="lp-about-image" variants={slideInFromLeft}>
                        <img src="/images/hero2.png" alt="About Sizzle" />
                    </ScrollReveal>
                    <ScrollReveal className="lp-about-content" variants={slideInFromRight}>
                        <motion.span className="lp-section-tag"
                            initial={{ opacity: 0, y: 10 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.4 }}
                        >
                            {t('about_tag')}
                        </motion.span>
                        <h2>{t('about_heading_1')}<br /><span className="lp-accent">{t('about_heading_2')}</span></h2>
                        <p>{t('about_desc')}</p>
                        <StaggerReveal className="lp-stats-row" variants={staggerContainer}>
                            <motion.div className="lp-stat" variants={staggerItem}>
                                <span className="lp-stat-value"><AnimatedNumber value={2400} prefix="" suffix="+" /></span>
                                <span className="lp-stat-label">{t('stat_restaurants')}</span>
                            </motion.div>
                            <motion.div className="lp-stat" variants={staggerItem}>
                                <span className="lp-stat-value"><AnimatedNumber value={18} suffix="%" /></span>
                                <span className="lp-stat-label">{t('stat_uplift')}</span>
                            </motion.div>
                            <motion.div className="lp-stat" variants={staggerItem}>
                                <span className="lp-stat-value"><AnimatedNumber value={5} /></span>
                                <span className="lp-stat-label">{t('stat_languages')}</span>
                            </motion.div>
                        </StaggerReveal>
                    </ScrollReveal>
                </div>
            </section>

            {/* CTA */}
            <section className="lp-cta-section">
                <ScrollReveal variants={scaleIn}>
                    <h2>{t('cta_heading')}</h2>
                    <p>{t('cta_sub')}</p>
                    <motion.button
                        className="lp-cta"
                        onClick={() => navigate('/login')}
                        whileHover={{ scale: 1.05, y: -3 }}
                        whileTap={{ scale: 0.97 }}
                    >
                        {t('cta_btn')}
                    </motion.button>
                </ScrollReveal>
            </section>

            {/* Contact Section */}
            <section className="lp-contact-section" id="contact">
                <div className="lp-contact-inner">
                    <div className="lp-contact-info">
                        <span className="lp-section-tag">{t('contact_tag')}</span>
                        <h2>{t('contact_heading')}</h2>
                        <p>{t('contact_desc')}</p>
                        <div className="lp-contact-details">
                            <div className="lp-contact-item">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                                    <polyline points="22,6 12,13 2,6" />
                                </svg>
                                <span>hello@sizzle.ai</span>
                            </div>
                            <div className="lp-contact-item">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
                                </svg>
                                <span>+91 98765 43210</span>
                            </div>
                            <div className="lp-contact-item">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                                    <circle cx="12" cy="10" r="3" />
                                </svg>
                                <span>Pune, Maharashtra, India</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <ScrollReveal>
                <footer className="lp-footer">
                    <StaggerReveal className="lp-footer-inner" variants={staggerContainer}>
                        <motion.div className="lp-footer-brand" variants={staggerItem}>
                            <span className="lp-footer-logo">SIZZLE</span>
                            <p>{t('footer_desc')}</p>
                        </motion.div>
                        <motion.div className="lp-footer-links" variants={staggerItem}>
                            <div>
                                <h4>{t('footer_product')}</h4>
                                <a href="#features">Features</a>
                                <a href="#">Pricing</a>
                                <a href="#">API Docs</a>
                            </div>
                            <div>
                                <h4>{t('footer_company')}</h4>
                                <a href="/about">About</a>
                                <a href="#">Careers</a>
                                <a href="#">Blog</a>
                            </div>
                            <div>
                                <h4>{t('footer_support')}</h4>
                                <a href="#">Help Center</a>
                                <a href="#contact">Contact</a>
                                <a href="#">Status</a>
                            </div>
                        </motion.div>
                    </StaggerReveal>
                    <div className="lp-footer-bottom">
                        &copy; 2026 Sizzle Technologies Pvt. Ltd. All rights reserved.
                    </div>
                </footer>
            </ScrollReveal>
        </div>
    )
}
