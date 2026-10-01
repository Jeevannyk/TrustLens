"""Fixed user-facing strings used when our own code (not the model) has to speak:
fallbacks and risk-floor overrides. Keyed by language code; unknown codes use English."""

SUPPORTED_LANGUAGES = ("en", "kn", "hi")


def pick(table: dict, language: str):
    return table.get(language) or table["en"]


FALLBACK_SUMMARY = {
    "en": "We couldn't fully analyze this, so be careful. Don't share passwords, codes or money, and don't open any links until you've checked with the sender another way.",
    "kn": "ನಾವು ಇದನ್ನು ಸಂಪೂರ್ಣವಾಗಿ ವಿಶ್ಲೇಷಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ, ಆದ್ದರಿಂದ ಎಚ್ಚರಿಕೆಯಿಂದಿರಿ. ಪಾಸ್‌ವರ್ಡ್, ಕೋಡ್ ಅಥವಾ ಹಣವನ್ನು ಹಂಚಿಕೊಳ್ಳಬೇಡಿ ಮತ್ತು ಕಳುಹಿಸಿದವರನ್ನು ಬೇರೆ ಮಾರ್ಗದಲ್ಲಿ ಪರಿಶೀಲಿಸುವವರೆಗೆ ಯಾವುದೇ ಲಿಂಕ್ ತೆರೆಯಬೇಡಿ.",
    "hi": "हम इसका पूरा विश्लेषण नहीं कर सके, इसलिए सावधान रहें। पासवर्ड, कोड या पैसे साझा न करें, और भेजने वाले से किसी और तरीके से पुष्टि होने तक कोई लिंक न खोलें।",
}

FALLBACK_ACTIONS = {
    "en": [
        "Don't share passwords, OTPs or PINs.",
        "Don't click links or send money.",
        "Check with the sender through a number or app you already trust.",
    ],
    "kn": [
        "ಪಾಸ್‌ವರ್ಡ್, OTP ಅಥವಾ PIN ಹಂಚಿಕೊಳ್ಳಬೇಡಿ.",
        "ಲಿಂಕ್‌ಗಳನ್ನು ಕ್ಲಿಕ್ ಮಾಡಬೇಡಿ ಅಥವಾ ಹಣ ಕಳುಹಿಸಬೇಡಿ.",
        "ನಿಮಗೆ ತಿಳಿದ ನಂಬಿಕಸ್ಥ ಸಂಖ್ಯೆ ಅಥವಾ ಆ್ಯಪ್ ಮೂಲಕ ಕಳುಹಿಸಿದವರನ್ನು ಪರಿಶೀಲಿಸಿ.",
    ],
    "hi": [
        "पासवर्ड, OTP या PIN साझा न करें।",
        "लिंक पर क्लिक न करें और पैसे न भेजें।",
        "भेजने वाले से किसी भरोसेमंद नंबर या ऐप से पुष्टि करें।",
    ],
}

FLOOR_SUMMARY = {
    "Suspicious": {
        "en": "Be careful with this message. Our checks found warning signs, so treat it as unsafe until you've confirmed it another way.",
        "kn": "ಈ ಸಂದೇಶದ ಬಗ್ಗೆ ಎಚ್ಚರಿಕೆ ವಹಿಸಿ. ನಮ್ಮ ಪರಿಶೀಲನೆಯಲ್ಲಿ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣಗಳು ಕಂಡುಬಂದಿವೆ, ಬೇರೆ ಮಾರ್ಗದಲ್ಲಿ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳುವವರೆಗೆ ಇದನ್ನು ಅಸುರಕ್ಷಿತವೆಂದು ಪರಿಗಣಿಸಿ.",
        "hi": "इस संदेश से सावधान रहें। हमारी जाँच में चेतावनी के संकेत मिले हैं, इसलिए किसी और तरीके से पुष्टि होने तक इसे असुरक्षित मानें।",
    },
    "Dangerous": {
        "en": "This looks dangerous. Our checks found strong signs of a scam, so don't click anything or share any details.",
        "kn": "ಇದು ಅಪಾಯಕಾರಿಯಾಗಿ ಕಾಣುತ್ತದೆ. ನಮ್ಮ ಪರಿಶೀಲನೆಯಲ್ಲಿ ವಂಚನೆಯ ಬಲವಾದ ಲಕ್ಷಣಗಳು ಕಂಡುಬಂದಿವೆ, ಯಾವುದನ್ನೂ ಕ್ಲಿಕ್ ಮಾಡಬೇಡಿ ಅಥವಾ ವಿವರಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಬೇಡಿ.",
        "hi": "यह खतरनाक लगता है। हमारी जाँच में धोखाधड़ी के मज़बूत संकेत मिले हैं, इसलिए कुछ भी क्लिक न करें और कोई जानकारी साझा न करें।",
    },
}

UNREADABLE_SUMMARY = {
    "en": "We couldn't read anything useful in this file, image or video, so we can't say it's safe. Try a clearer screenshot, file or video, or paste the text.",
    # kn/hi video wording below needs native-speaker review.
    "kn": "ಈ ಫೈಲ್, ಚಿತ್ರ ಅಥವಾ ವೀಡಿಯೊದಲ್ಲಿ ಉಪಯುಕ್ತವಾದದ್ದನ್ನು ಓದಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ, ಆದ್ದರಿಂದ ಇದು ಸುರಕ್ಷಿತ ಎಂದು ಹೇಳಲು ಸಾಧ್ಯವಿಲ್ಲ. ಸ್ಪಷ್ಟವಾದ ಸ್ಕ್ರೀನ್‌ಶಾಟ್, ಫೈಲ್ ಅಥವಾ ವೀಡಿಯೊ ಪ್ರಯತ್ನಿಸಿ, ಅಥವಾ ಪಠ್ಯವನ್ನು ಅಂಟಿಸಿ.",
    "hi": "हम इस फ़ाइल, तस्वीर या वीडियो में कुछ काम का नहीं पढ़ सके, इसलिए इसे सुरक्षित नहीं कह सकते। साफ़ स्क्रीनशॉट, फ़ाइल या वीडियो आज़माएँ, या टेक्स्ट पेस्ट करें।",
}

SAFE_FINDING = {
    "en": "Nothing in this message asks for money, codes, passwords or links.",
    "kn": "ಈ ಸಂದೇಶವು ಹಣ, ಕೋಡ್, ಪಾಸ್‌ವರ್ಡ್ ಅಥವಾ ಲಿಂಕ್‌ಗಳನ್ನು ಕೇಳುವುದಿಲ್ಲ.",
    "hi": "इस संदेश में पैसे, कोड, पासवर्ड या लिंक माँगने जैसी कोई बात नहीं है।",
}

FLAG_TITLES = {
    "safe_browsing": {
        "en": "Flagged as a known dangerous site",
        "kn": "ತಿಳಿದಿರುವ ಅಪಾಯಕಾರಿ ಸೈಟ್ ಎಂದು ಗುರುತಿಸಲಾಗಿದೆ",
        "hi": "ज्ञात खतरनाक साइट के रूप में चिह्नित",
    },
    "lookalike": {
        "en": "Link imitates a real brand",
        "kn": "ಲಿಂಕ್ ನಿಜವಾದ ಬ್ರ್ಯಾಂಡ್ ಅನ್ನು ಅನುಕರಿಸುತ್ತದೆ",
        "hi": "लिंक असली ब्रांड की नकल करता है",
    },
    "new_domain": {
        "en": "Website was created very recently",
        "kn": "ವೆಬ್‌ಸೈಟ್ ಇತ್ತೀಚೆಗೆ ರಚಿಸಲಾಗಿದೆ",
        "hi": "वेबसाइट हाल ही में बनाई गई है",
    },
    "sensitive_request": {
        "en": "Asks you to hand over private details",
        "kn": "ನಿಮ್ಮ ಖಾಸಗಿ ವಿವರಗಳನ್ನು ಕೇಳುತ್ತದೆ",
        "hi": "आपकी निजी जानकारी माँगता है",
    },
    "injection": {
        "en": "Tries to manipulate the checker",
        "kn": "ಪರಿಶೀಲನೆಯನ್ನು ಬದಲಿಸಲು ಯತ್ನಿಸುತ್ತದೆ",
        "hi": "जाँच को प्रभावित करने की कोशिश करता है",
    },
    "suspicious_link": {
        "en": "Link has warning signs",
        "kn": "ಲಿಂಕ್‌ನಲ್ಲಿ ಎಚ್ಚರಿಕೆಯ ಲಕ್ಷಣಗಳಿವೆ",
        "hi": "लिंक में चेतावनी के संकेत हैं",
    },
}
