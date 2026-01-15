"""AI-powered prompt generation for image and video content.

This module implements a two-stage pipeline where Claude generates optimized
prompts for Higgsfield's image/video models, resulting in more realistic
and contextually appropriate influencer content.
"""

from typing import Optional, Dict, Any, List
import structlog
import random

from app.models.persona import Persona
from app.services.ai.base import Message
from app.services.ai.anthropic_provider import AnthropicProvider

logger = structlog.get_logger()


# =============================================================================
# META-PROMPTS: Teaching Claude how to write great prompts for Higgsfield
# =============================================================================

IMAGE_META_PROMPT = """You are an expert at writing prompts for AI image generation, specifically for creating realistic social media influencer content.

Your job is to write a single, optimized prompt for Higgsfield's Soul model that will generate an authentic-looking influencer photo.

CRITICAL RULES FOR REALISTIC INFLUENCER PHOTOS:

1. FRAMING & COMPOSITION (VERY IMPORTANT):
   - PREFER close-up (face/shoulders), medium shots (waist-up), or seated poses
   - For selfies: frame from chest/shoulders up - NEVER full body selfies
   - For mirror shots: waist-up or sitting on bed - avoid standing full body
   - NEVER describe full body standing shots - these cause missing limbs/feet issues
   - If legs are in frame, subject should be sitting/lying so legs are bent, not standing

2. NO CAMERA EQUIPMENT (VERY IMPORTANT):
   - DO NOT show any phone, camera, tripod, or recording equipment in the image
   - DO NOT show her holding a phone or any device
   - Both of her hands are FREE and empty
   - She can have hands on hips, touching hair, at her sides, or gesturing
   - State: "No phone, no tripod, no camera equipment visible. Both hands free and empty."

3. HANDS (CRITICAL):
   - Both hands should be FREE (not holding phone)
   - Keep hand positions SIMPLE: on hips, touching hair, at sides, behind back
   - NEVER describe hands doing detailed things or holding objects
   - Say "both hands free, relaxed natural position"

4. FACE & APPEARANCE CONSISTENCY:
   - ALWAYS include ethnicity (e.g., "young mixed race woman, about 25 years old")
   - ALWAYS include hair type (e.g., "curly, naturally styled hair with blonde highlights")
   - Do NOT describe specific facial features (eye shape, nose shape, lip shape)
   - The character reference handles specific facial features
   - Describe EXPRESSION (smiling, playful look, confident gaze)
   - Include: ethnicity + hair type + body type + expression
   - Exclude: eye color, nose shape, lip shape, face shape

5. CAPTURE STYLE: 
   - Casual phone-quality photo aesthetic (slight imperfections, not studio perfect)
   - Never professional camera/DSLR quality
   - No camera equipment visible in the shot

6. LIGHTING:
   - Ring lights, natural window light, bathroom vanity lights, golden hour
   - Never studio lighting

7. ENVIRONMENT:
   - Real, lived-in spaces - messy beds, products on counters
   - Never sterile/perfect sets

8. NO TEXT: Always state "NO text, NO watermarks, NO overlays"

STRUCTURE YOUR PROMPT:
- Start with "NO TEXT, NO watermarks, NO overlays. No phone, no tripod, no camera equipment visible. Both hands free and empty."
- Describe framing (close-up, medium shot, waist-up)
- Describe subject with ethnicity, hair, body type
- Describe setting/environment
- Describe lighting and expression
- Describe simple hand position (on hips, at sides, touching hair, etc.) - hands are EMPTY
- End with: "AVOID: full body standing shots, detailed hands, any camera equipment, phone, tripod, selfie stick, ring light in frame"

OUTPUT FORMAT:
Return ONLY the prompt text. No explanations, no JSON - just the raw prompt string."""


VIDEO_META_PROMPT = """You are an expert at writing motion prompts for AI video generation, specifically for creating realistic 5-6 second influencer video clips.

Your job is to write a motion prompt for Higgsfield's Wan model that will generate authentic-looking influencer video content.

CRITICAL RULES FOR REALISTIC INFLUENCER VIDEOS:

1. SPEECH PATTERN (VERY IMPORTANT - prevents gibberish):
   - She says the PRIMARY phrase first (2-3 seconds)
   - Then she says a SHORT FOLLOW-UP phrase (1-2 seconds) - this fills dead space naturally
   - After the follow-up, she can smile/react briefly
   - The follow-up should be natural like: "yeah!", "let's go!", "love you guys!", "so excited!", "trust me!", "right?"
   - EXPLICITLY STATE: "After saying [follow-up], she STOPS talking completely. No more words."

2. VOICE/ACCENT (IMPORTANT FOR CONSISTENCY):
   - ALWAYS specify the voice accent in the prompt (e.g., "speaking with an American accent")
   - This ensures consistent voice across all videos
   - Include this right after describing what she says

3. NO CAMERA EQUIPMENT (VERY IMPORTANT):
   - DO NOT show any phone, camera, tripod, or recording equipment in the video
   - DO NOT show her holding a phone or any device
   - Both of her hands are FREE and empty - she can gesture naturally
   - She is NOT holding anything
   - State: "No phone, no tripod, no camera equipment visible. Both hands free and empty."

4. FRAMING (prevents missing limbs):
   - ALWAYS specify "medium shot, waist-up" or "close-up on face and shoulders"
   - NEVER describe full body shots in videos
   - Subject should be seated or framed from waist up

5. FACE & APPEARANCE CONSISTENCY:
   - ALWAYS include ethnicity (e.g., "young mixed race woman, about 25 years old")
   - ALWAYS include hair type (e.g., "curly, naturally styled hair with blonde highlights")
   - Do NOT describe specific facial features (eye shape, nose shape)
   - Character reference handles specific facial features
   - Focus on: expressions, smile, eye contact, head tilts

6. HANDS:
   - Both hands should be FREE (not holding phone)
   - Hands can gesture naturally while talking
   - Or hands can be on hips, touching hair, or resting naturally
   - Keep hand poses SIMPLE - avoid detailed finger positions

7. MOTION:
   - Natural micro-movements: breathing, weight shifts, hair movement, blinks
   - Natural hand gestures while speaking
   - Never robotic or frozen

8. NO TEXT: "NO text overlays, NO captions on screen"

STRUCTURE YOUR PROMPT:
- Start with "NO TEXT on screen, NO captions, NO overlays. Medium shot, waist-up framing. No phone, no tripod, no camera equipment visible. Both hands free and empty."
- Specify: "She says: '[primary phrase]' then '[follow-up phrase]' in a [accent] accent"
- Explicitly state: "After '[follow-up]', she STOPS talking - just smiles at camera. No more words, no gibberish."
- Describe setting and lighting
- Describe natural motion, expressions, and hand gestures (hands are EMPTY)
- Describe audio (room tone, not silence)
- End with: "AVOID: AI artifacts, morphing, full body shots, gibberish speech, robotic movement, any camera equipment, phone, tripod, selfie stick"

OUTPUT FORMAT:
Return ONLY the motion prompt text. No explanations, no JSON."""


NSFW_IMAGE_META_PROMPT = """You are an expert at writing prompts for intimate/adult content generation for platforms like Fanvue.

Your job is to write prompts that create authentic-looking, self-captured intimate photos.

CRITICAL RULES FOR REALISTIC INTIMATE CONTENT:

1. FRAMING & COMPOSITION (VERY IMPORTANT):
   - PREFER: lying on bed, sitting poses, kneeling, waist-up mirror selfies
   - For lying down: bent legs are fine, full stretched legs can have issues
   - For sitting: legs can be visible if bent/tucked
   - AVOID: standing full body shots - these cause missing feet/legs
   - AVOID: complex poses with extended limbs

2. NO CAMERA EQUIPMENT (VERY IMPORTANT):
   - DO NOT show any phone, camera, tripod, or recording equipment in the image
   - DO NOT show her holding a phone or any device
   - Both of her hands are FREE and empty
   - Her hands can be on her body naturally (hip, thigh, hair)
   - State: "No phone, no tripod, no camera equipment visible. Both hands free."

3. HANDS (CRITICAL):
   - Both hands are FREE (not holding phone)
   - Keep hand positions SIMPLE: on body (hip, thigh, hair), resting naturally
   - NEVER describe hands doing detailed things
   - Say explicitly: "both hands free, simple natural position"

4. FACE & APPEARANCE CONSISTENCY:
   - ALWAYS include ethnicity (e.g., "young mixed race woman, about 25 years old")
   - ALWAYS include hair type (e.g., "curly, naturally styled hair with blonde highlights")
   - Do NOT describe specific facial features (eye shape, nose shape)
   - Describe EXPRESSION: seductive look, playful smile, eye contact
   - Character reference handles specific facial features

5. CAPTURE: Phone timer shot from propped position - NOT handheld selfie

6. SETTING: Real bedrooms, bathrooms - rumpled sheets, personal items visible

7. LIGHTING: Bedside lamps, ring lights, natural window light

8. CLOTHING: Describe lingerie/clothing and natural reveals

9. NO TEXT: "NO text, NO watermarks"

STRUCTURE YOUR PROMPT:
- Start with "NO TEXT, NO watermarks. No phone, no tripod, no camera equipment visible. Both hands free. [Framing: e.g., 'Lying on bed' or 'Seated on edge of bed']"
- Describe subject with ethnicity, hair, body type - NOT specific facial features
- Describe outfit and what it reveals
- Describe pose with both hands FREE, empty, and in simple position
- Describe setting with authentic details
- Describe lighting and expression
- End with: "AVOID: standing full body shots, detailed hands, any camera equipment, phone, tripod, selfie stick, specific facial features"

OUTPUT FORMAT:
Return ONLY the prompt text. No explanations."""


NSFW_VIDEO_META_PROMPT = """You are an expert at writing motion prompts for intimate/adult video content for platforms like Fanvue.

Your job is to write motion prompts that create authentic-looking, self-recorded intimate video clips.

CRITICAL RULES FOR REALISTIC INTIMATE VIDEOS:

1. FRAMING (VERY IMPORTANT):
   - ALWAYS: "Medium shot showing from hips/waist up" or "Close-up on upper body"
   - Subject should be: lying down, seated, or kneeling - NOT standing full body
   - This prevents missing limbs/feet issues

2. NO CAMERA EQUIPMENT (VERY IMPORTANT):
   - DO NOT show any phone, camera, tripod, or recording equipment in the video
   - DO NOT show her holding a phone or any device
   - Both of her hands are FREE and empty to move naturally
   - She is NOT holding anything
   - State: "No phone, no tripod, no camera equipment visible. Both hands free."

3. VOICE/ACCENT (IMPORTANT FOR CONSISTENCY):
   - If the video includes speech or moans, specify the accent
   - Example: "soft sounds with American accent" or "whispered words in American accent"
   - This ensures consistent voice across all videos

4. HANDS:
   - Both hands are FREE (not holding phone)
   - Keep hand movements SIMPLE: running along body, touching hair, on hips
   - Don't describe detailed finger movements
   - Hands can be partially out of frame

5. FACE & APPEARANCE:
   - ALWAYS include ethnicity and hair type
   - Don't describe specific facial features (eye shape, nose shape)
   - Focus on: expression, eye contact, reactions
   - Character reference handles specific facial features

6. MOTION:
   - Slow, sensual movements
   - Natural breathing visible
   - Subtle fabric shifts
   - Teasing gestures with free hands

7. AUDIO: Soft breathing, fabric sounds, room ambiance - NO music

8. NO TEXT: "NO text overlays, NO captions"

STRUCTURE YOUR PROMPT:
- Start with "NO TEXT, NO overlays. Medium shot, waist-up framing. No phone, no tripod, no camera equipment visible. Both hands free and empty."
- Describe subject and outfit
- Describe setting
- Describe motion sequence (keep hand actions simple, hands are FREE and EMPTY)
- Describe audio (include accent if any speech/sounds)
- Describe camera feel
- End with: "AVOID: full body shots, detailed hands, AI morphing, robotic movement, any camera equipment, phone, tripod, selfie stick"

OUTPUT FORMAT:
Return ONLY the motion prompt text."""


# =============================================================================
# USER TEMPLATES: Context for each generation request
# =============================================================================

IMAGE_USER_TEMPLATE = """Write an image generation prompt for this influencer:

PERSONA:
- Name: {name}
- Niche: {niche}
- Appearance: {appearance_description}

CONTENT CONTEXT:
- Platform: {platform}
- Content Type: {content_type}
- Caption/Topic: {caption}
- Mood: {mood}

CRITICAL REQUIREMENTS:
- NO phone, tripod, camera, or any recording equipment visible in the image
- Both of her hands are FREE and EMPTY - she is NOT holding anything
- Her hands can be on hips, touching hair, at sides, or gesturing naturally
- Use {framing_suggestion} framing to avoid body part issues
- INCLUDE ethnicity and hair type from the appearance description above
- Don't describe specific facial features like eye shape, nose shape (character reference handles those)
- Focus on expression and vibe

Generate a prompt for a realistic {content_type} with NO camera equipment visible."""


VIDEO_USER_TEMPLATE = """Write a video motion prompt for this content:

PERSONA:
- Name: {name}
- Niche: {niche}
- Appearance: {appearance_description}
- Voice/Accent: {voice_accent}

VIDEO CONTEXT:
- Platform: {platform}
- Setting/Location: {setting}
- Primary phrase she says: "{speech_phrase}"
- Follow-up phrase to fill time: "{followup_phrase}"
- Mood: {mood}

CRITICAL REQUIREMENTS:
- NO phone, tripod, camera, or any recording equipment visible in the video
- Both of her hands are FREE and EMPTY - she is NOT holding anything
- She can gesture naturally with her free hands while talking
- She says the primary phrase, then the follow-up phrase, then goes SILENT (smiles)
- SPECIFY THE ACCENT: She speaks with a {voice_accent} accent
- Use medium shot (waist-up) framing
- INCLUDE ethnicity and hair type from appearance description
- Don't describe specific facial features (character reference handles those)
- After both phrases, explicitly state NO MORE TALKING to prevent gibberish

Generate a motion prompt for a realistic 5-6 second video clip with NO camera equipment visible."""


NSFW_IMAGE_USER_TEMPLATE = """Write an intimate image prompt for this content creator:

PERSONA:
- Name: {name}
- Appearance: {appearance_description}

CONTENT CONTEXT:
- Platform: Fanvue
- Setting: {setting}
- Outfit/Clothing: {outfit}
- Pose: {pose}
- Mood: {mood}

CRITICAL REQUIREMENTS:
- NO phone, tripod, camera, or any recording equipment visible in the image
- Both of her hands are FREE and EMPTY - she is NOT holding anything
- Her hands can be on her body (hip, thigh, hair) - keep positions SIMPLE
- Use pose that avoids standing full body (lying/sitting/kneeling preferred)
- INCLUDE ethnicity and hair type from appearance description
- Don't describe specific facial features (character reference handles those)
- Focus on expression and sensuality

Generate a prompt for a realistic intimate photo with NO camera equipment visible."""


NSFW_VIDEO_USER_TEMPLATE = """Write an intimate video motion prompt for this content creator:

PERSONA:
- Name: {name}
- Appearance: {appearance_description}
- Voice/Accent: {voice_accent}

VIDEO CONTEXT:
- Platform: Fanvue
- Setting: {setting}
- Outfit/Clothing: {outfit}
- Motion/Action: {motion_description}
- Mood: {mood}

CRITICAL REQUIREMENTS:
- NO phone, tripod, camera, or any recording equipment visible in the video
- Both of her hands are FREE and EMPTY - she is NOT holding anything
- Her hands can move naturally on her body
- Use medium shot (waist-up) framing
- Keep hand movements simple
- INCLUDE ethnicity and hair type from appearance description
- Don't describe specific facial features (character reference handles those)
- If any sounds/moans/speech: use {voice_accent} accent

Generate a motion prompt for a realistic 5-second intimate video clip with NO camera equipment visible."""


# =============================================================================
# SUPPORTING DATA: Settings, moods, outfits, follow-up phrases
# =============================================================================

# Follow-up phrases to fill video dead space naturally
VIDEO_FOLLOWUP_PHRASES = [
    "Yeah!",
    "Let's go!",
    "Love you guys!",
    "So excited!",
    "Trust me!",
    "Right?",
    "Okay!",
    "Yes!",
    "Seriously!",
    "You know?",
    "For real!",
    "I mean it!",
    "Come on!",
    "Woo!",
    "Bye!",
]

# Framing suggestions for different content types (avoid full body)
FRAMING_SUGGESTIONS = {
    "selfie": "close-up, face and shoulders",
    "mirror": "waist-up mirror shot",
    "post": "medium shot, waist-up",
    "story": "close-up selfie style",
    "reel": "medium shot, seated or waist-up",
    "video_frame": "medium shot, waist-up or seated",
}

# =============================================================================
# NSFW CONTENT ARRAYS (for Fanvue) - Expanded for variety
# =============================================================================

NSFW_SETTINGS = [
    # Bedroom variations
    "cozy bedroom with rumpled sheets and bedside lamp glow",
    "bed with morning sunlight through curtains",
    "bedroom with ring light and warm ambiance",
    "luxurious bedroom with satin sheets and soft lighting",
    "minimalist bedroom with white sheets and natural light",
    "bohemian bedroom with fairy lights and cozy blankets",
    "master bedroom with floor-to-ceiling windows at sunset",
    "hotel suite bed with crisp white linens",
    "penthouse bedroom with city night view",
    "cozy cabin bedroom with fireplace glow",
    # Bathroom variations
    "bathroom mirror with warm vanity lighting",
    "bathtub with candles and steam",
    "spa-like bathroom with soft ambient glow",
    "modern bathroom with sleek fixtures and warm lighting",
    "bathroom with bubble bath and rose petals",
    "luxury bathroom with marble and gold fixtures",
    # Hotel/Travel
    "hotel room bed with city lights through window",
    "boutique hotel room with vintage decor",
    "penthouse suite with panoramic city view at night",
    "tropical resort room with ocean breeze",
    "five-star hotel with luxe bedding",
    # Living spaces
    "living room couch with soft afternoon light",
    "plush sectional sofa with dim mood lighting",
    "reading nook with warm lamp light",
    "cozy fireplace setting with soft rug",
    "modern loft with exposed brick and soft lighting",
    # Outdoor/Private
    "private balcony at golden hour",
    "rooftop terrace at dusk",
    "private pool area at sunset",
    "secluded beach cabana",
    "private yacht cabin",
    "tropical villa bedroom",
]

NSFW_OUTFITS = [
    # Classic lingerie
    "black lace bra and matching panties",
    "red lingerie set with garter straps",
    "white cotton bralette and boy shorts",
    "lace teddy with revealing cutouts",
    "sheer bodysuit that clings to her curves",
    "burgundy velvet bra and thong set",
    "emerald green satin lingerie",
    "blush pink mesh lingerie set",
    "navy blue lace bralette and hipsters",
    "leopard print lingerie set",
    "champagne colored silk lingerie",
    "dusty rose lace ensemble",
    "midnight black corset and panties",
    "ivory bridal-style lingerie",
    # Robes and sleepwear
    "silk robe loosely tied, falling off one shoulder",
    "satin slip dress riding up her thighs",
    "oversized t-shirt that barely covers, no pants",
    "cozy sweater worn off-shoulder with just panties",
    "sheer kimono robe with nothing underneath",
    "short satin nightgown",
    "cropped sleep tank and tiny shorts",
    "luxe velvet robe",
    "lace-trimmed chemise",
    # Athletic/Casual sexy
    "sports bra and yoga shorts",
    "cropped workout top and thong",
    "mesh workout set showing skin underneath",
    "bikini top and unbuttoned jean shorts",
    "tank top and lace underwear",
    # Minimal/Implied
    "wrapped loosely in bedsheet",
    "oversized button-up shirt barely buttoned",
    "just a towel wrapped around her",
    "boyfriend's dress shirt, unbuttoned",
    "cashmere throw draped strategically",
]

# Updated poses to avoid standing full body
NSFW_POSES = [
    # Lying down
    "lying on bed looking up at camera, legs bent casually",
    "lying on side with hand on hip, knees bent",
    "lying back on pillows, relaxed and inviting",
    "lying on stomach, looking over shoulder",
    "stretched out on bed, one knee bent",
    "lying with head at edge of bed, looking up",
    "curled up on side with playful expression",
    # Sitting
    "sitting on edge of bed, leaning forward",
    "sitting cross-legged on bed with playful expression",
    "sitting up in bed with sheets around waist",
    "perched on bed with legs tucked under",
    "sitting on floor leaning against bed",
    "seated on vanity chair",
    "sitting in bathtub with bubbles",
    # Kneeling
    "kneeling on bed with playful expression",
    "kneeling on bed adjusting outfit strap",
    "kneeling with hands on thighs",
    "kneeling on soft rug",
    # Mirror/Selfie style
    "waist-up mirror selfie adjusting her outfit",
    "mirror shot from bed, relaxed pose",
    "close-up from above, lying on back",
    # Other
    "looking over shoulder at camera, seated",
    "stretching in bed, just waking up",
    "reclining against pillows",
    "lounging on chaise",
]

NSFW_MOODS = [
    "playful and teasing",
    "sultry and confident",
    "soft and romantic",
    "bold and seductive",
    "intimate and personal",
    "flirty morning vibes",
    "mysteriously alluring",
    "sweet and innocent",
    "wild and uninhibited",
    "sensual and dreamy",
    "coy and flirtatious",
    "warm and inviting",
    "powerful and in control",
    "vulnerable and open",
    "mischievous and fun",
]

NSFW_MOTIONS = [
    "slowly adjusts her outfit revealing more skin, maintains eye contact",
    "lies back on pillows, runs hand along her side",
    "turns slightly, fabric slips to show more shoulder",
    "stretches sensually on bed, arching back slightly",
    "sits up slowly, letting robe fall open more",
    "playfully tugs at clothing strap with a teasing smile",
    "shifts position on bed, sheet sliding to reveal thigh",
    "runs fingers through her hair while making eye contact",
    "slowly rolls onto her side, fabric falling naturally",
    "adjusts pillow behind her, outfit shifting seductively",
    "gentle hip movement while lying on side",
    "traces finger along collarbone with a smirk",
    "bites lip playfully while adjusting position",
    "stretches arms overhead sensually",
    "slowly pulls sheet up to chin then lets it fall",
]

# =============================================================================
# SFW CONTENT ARRAYS (for Instagram/general social media) - Expanded for variety
# =============================================================================

SFW_SETTINGS = [
    # Home/Indoor - Morning
    "bedroom with golden morning light streaming through curtains",
    "cozy bed with white linens and morning sunshine",
    "bathroom vanity with bright natural light",
    "sunlit kitchen making breakfast",
    "home gym corner with morning light",
    "breakfast nook with coffee",
    # Home/Indoor - Day
    "living room couch with soft afternoon sun",
    "home office with clean aesthetic",
    "yoga corner with plants and natural light",
    "bedroom mirror with ring light",
    "modern apartment with floor-to-ceiling windows",
    "reading corner with good lighting",
    "organized closet for outfit selection",
    # Fitness locations
    "modern gym with sleek equipment and good lighting",
    "boutique fitness studio with ambient lighting",
    "yoga studio with warm wood floors",
    "spin class with dramatic mood lighting",
    "boxing gym with industrial vibes",
    "crossfit box with gritty aesthetic",
    "pilates reformer studio",
    "weight room with mirrors",
    "cardio floor with treadmills",
    "stretching area with foam rollers",
    "functional training zone",
    # Outdoor fitness
    "outdoor track at golden hour",
    "beach boardwalk at sunrise for run",
    "park path with autumn leaves",
    "rooftop workout space with city skyline",
    "outdoor stairs for training",
    "hiking trail with scenic view",
    "beach for sand workout",
    "tennis court at sunset",
    "basketball court with good lighting",
    "swimming pool lane for laps",
    "mountain trail rest point",
    "scenic running path",
    # Fashion/Shopping
    "boutique dressing room with flattering lighting",
    "trendy cafe with aesthetic decor",
    "street style with urban backdrop",
    "high-end shopping district",
    "vintage store with unique finds",
    "department store mirror",
    "shoe store trying on heels",
    # Coffee/Food/Lifestyle
    "aesthetic coffee shop with plants",
    "brunch spot with natural lighting",
    "healthy smoothie bar counter",
    "farmers market exploring",
    "rooftop restaurant at sunset",
    "juice bar with colorful backdrop",
    "acai bowl cafe",
    "health food store",
    # Travel/Lifestyle
    "hotel room with city view",
    "beach with palm trees background",
    "poolside lounge area",
    "airport lounge style",
    "scenic overlook point",
    "urban rooftop at golden hour",
    "resort lobby",
    "tropical destination",
    # Car/Transport
    "car interior with natural light",
    "parked convertible at beach",
    "uber/taxi heading somewhere",
    # Wellness/Self-care
    "spa-like bathroom with candles",
    "meditation corner with cushions",
    "skincare routine setup",
    "bubble bath relaxation moment",
    "face mask selfie",
    "journaling corner",
    # Night/Evening
    "getting ready for night out",
    "restaurant dinner ambiance",
    "bar with mood lighting",
    "concert or event venue",
]

SFW_MOODS = [
    # Energetic/Active
    "energetic and motivated",
    "pumped up and determined",
    "fierce and focused",
    "powerful and strong",
    "athletic and driven",
    "ready to crush it",
    "unstoppable energy",
    "post-workout high",
    # Relaxed/Casual
    "casual and relaxed",
    "cozy and content",
    "laid-back and chill",
    "peaceful and serene",
    "comfortable and at ease",
    "sunday vibes",
    "lazy day mood",
    # Confident/Happy
    "confident and happy",
    "radiant and glowing",
    "proud and accomplished",
    "joyful and bright",
    "self-assured and bold",
    "feeling myself",
    "main character energy",
    "boss babe vibes",
    # Thoughtful/Calm
    "thoughtful and peaceful",
    "introspective and calm",
    "mindful and present",
    "grateful and grounded",
    "zen and centered",
    # Playful/Fun
    "excited and cheerful",
    "playful and fun",
    "silly and goofy",
    "flirty and cute",
    "adventurous and free",
    "weekend mood",
    "girls trip vibes",
    # Professional/Polished
    "sleek and polished",
    "professional and put-together",
    "sophisticated and elegant",
    "chic and stylish",
]

# =============================================================================
# NICHE-SPECIFIC SETTINGS (expanded for fitness/fashion/modeling)
# =============================================================================

FITNESS_SETTINGS = [
    # Gym environments
    "modern gym with sleek equipment",
    "weight room with dumbbells and mirrors",
    "cardio area with treadmills and bikes",
    "functional fitness area with kettlebells",
    "stretching zone with yoga mats",
    "boxing area with heavy bags",
    "spin studio with mood lighting",
    "crossfit box with pull-up bars",
    "powerlifting platform with barbells",
    "cable machine station",
    "squat rack area",
    "leg press machine",
    "smith machine station",
    "dumbbell rack mirror",
    "battle ropes area",
    # Home gym
    "home gym setup with minimal equipment",
    "garage gym with raw aesthetic",
    "apartment workout corner",
    "living room cleared for workout",
    "balcony workout space",
    # Outdoor fitness
    "outdoor track at sunrise",
    "beach sand training area",
    "park with workout bars",
    "hiking trail rest point",
    "stadium stairs workout",
    "tennis court session",
    "basketball court training",
    "running path in nature",
    "outdoor bootcamp setup",
    "trail running vista",
    # Recovery/Wellness
    "foam rolling recovery area",
    "post-workout locker room",
    "sauna relaxation session",
    "ice bath recovery",
    "massage gun session",
    "stretching post-workout",
    "yoga cooldown",
    # Nutrition related
    "kitchen prepping healthy meal",
    "blender making protein shake",
    "meal prep containers spread",
    "healthy breakfast setup",
    "smoothie bowl creation",
    "grocery haul display",
    "supplement stack",
]

FASHION_SETTINGS = [
    # Shopping/Retail
    "boutique dressing room mirror",
    "designer store fitting room",
    "vintage shop treasure hunt",
    "department store mirror check",
    "outlet mall shopping spree",
    "thrift store styling finds",
    "luxury store shopping bag moment",
    "showroom private viewing",
    # Getting ready
    "bedroom mirror full outfit check",
    "bathroom vanity makeup session",
    "closet organization showing collection",
    "jewelry selection process",
    "shoe closet trying on options",
    "handbag collection display",
    "hat wall selection",
    # Street style
    "urban sidewalk with graffiti background",
    "trendy neighborhood aesthetic street",
    "cafe outdoor seating fashion shot",
    "city skyline golden hour",
    "colorful mural wall backdrop",
    "iconic landmark fashion moment",
    "cobblestone street european vibes",
    "palm tree lined boulevard",
    # Events/Occasions
    "red carpet preparation moment",
    "backstage fashion show chaos",
    "photo studio setup professional",
    "magazine shoot behind scenes",
    "fashion week venue entrance",
    "gala event getting ready",
    "wedding guest outfit prep",
    # Lifestyle fashion
    "brunch table aesthetic",
    "rooftop party mingling",
    "beach resort pool style",
    "ski lodge après-ski look",
    "music festival boho vibes",
    "date night restaurant ready",
    "girls night glam prep",
    "vacation packing flat lay",
    # Home fashion content
    "cozy athleisure home moment",
    "work from home chic outfit",
    "loungewear lazy sunday",
    "pajama set cozy vibes",
]

MODELING_SETTINGS = [
    # Studio professional
    "professional photo studio white backdrop",
    "colored gel lighting editorial studio",
    "natural light studio with windows",
    "editorial set design styled",
    "beauty dish lighting setup",
    "ring light portrait studio",
    # Location shoots outdoor
    "rooftop with dramatic city views",
    "beach at golden hour waves",
    "desert landscape dramatic sky",
    "forest clearing dappled light",
    "flower field spring vibes",
    "snowy mountain backdrop",
    # Location shoots urban
    "industrial warehouse aesthetic",
    "abandoned building editorial",
    "neon-lit urban night scene",
    "classic architecture columns",
    "graffiti wall street style",
    "modern architecture geometric",
    "parking garage edgy vibes",
    # Fashion forward
    "runway show backstage prep",
    "haute couture fitting session",
    "designer showroom exclusive",
    "fashion editorial dramatic set",
    "lookbook clean backdrop",
    # Beauty/Portrait specific
    "ring light beauty close-up setup",
    "softbox portrait dramatic lighting",
    "window light portrait natural",
    "dramatic shadow play portrait",
    "makeup artist chair glam",
    # Lifestyle luxury modeling
    "luxury hotel suite editorial",
    "yacht deck lifestyle shoot",
    "private jet interior luxury",
    "sports car model moment",
    "penthouse terrace city views",
    "mansion grounds editorial",
    "infinity pool resort",
    "champagne lifestyle moment",
]


class AIPromptGenerator:
    """Generate optimized prompts using AI for image/video generation.
    
    This service uses Claude to craft intelligent, context-aware prompts
    for Higgsfield's image and video models, resulting in more realistic
    and authentic influencer content.
    """
    
    def __init__(self):
        """Initialize the prompt generator with Anthropic provider."""
        self.provider = AnthropicProvider()
    
    # Default appearance values (used only if persona fields are not set)
    DEFAULT_APPEARANCE = {
        "ethnicity": "mixed race",
        "hair": "curly, naturally styled hair with blonde highlights",
        "body": "fit and toned",
        "age": "25 years old",
    }
    
    def _get_appearance_description(self, persona: Persona) -> str:
        """Get appearance description from persona's appearance fields.
        
        Reads from persona.appearance_ethnicity, appearance_age, appearance_hair,
        and appearance_body_type fields. Falls back to defaults if not set.
        
        Includes ethnicity and hair type for consistency, but avoids 
        specific facial features (which the character reference handles).
        """
        # Get appearance from persona fields, with fallbacks to defaults
        ethnicity = getattr(persona, 'appearance_ethnicity', None) or self.DEFAULT_APPEARANCE["ethnicity"]
        age = getattr(persona, 'appearance_age', None) or self.DEFAULT_APPEARANCE["age"]
        hair = getattr(persona, 'appearance_hair', None) or self.DEFAULT_APPEARANCE["hair"]
        body = getattr(persona, 'appearance_body_type', None) or self.DEFAULT_APPEARANCE["body"]
        
        return f"young {ethnicity} woman, about {age}, with {hair}, {body}"
    
    def _get_body_type(self, persona: Persona) -> str:
        """Get body type description from persona's appearance field."""
        body = getattr(persona, 'appearance_body_type', None) or self.DEFAULT_APPEARANCE["body"]
        return f"{body} with natural curves"
    
    def _get_framing_for_content_type(self, content_type: str) -> str:
        """Get appropriate framing suggestion to avoid body part issues."""
        return FRAMING_SUGGESTIONS.get(content_type, "medium shot, waist-up")
    
    def _get_followup_phrase(self, primary_phrase: str) -> str:
        """Select an appropriate follow-up phrase based on the primary phrase."""
        primary_lower = primary_phrase.lower()
        
        # Match follow-up to primary phrase tone
        if any(word in primary_lower for word in ["love", "excited", "happy", "amazing"]):
            return random.choice(["So excited!", "Love you guys!", "Yes!", "Woo!"])
        elif any(word in primary_lower for word in ["do this", "go", "start", "let's"]):
            return random.choice(["Let's go!", "Yeah!", "Come on!", "Woo!"])
        elif any(word in primary_lower for word in ["trust", "believe", "know", "real"]):
            return random.choice(["Trust me!", "For real!", "Seriously!", "I mean it!"])
        elif any(word in primary_lower for word in ["?", "right", "yeah"]):
            return random.choice(["Right?", "You know?", "Yeah!", "Okay!"])
        else:
            return random.choice(VIDEO_FOLLOWUP_PHRASES)
    
    def _select_setting_for_niche(self, niche: list, is_nsfw: bool = False) -> str:
        """Select an appropriate setting based on persona's niche."""
        niche_lower = [n.lower() for n in niche]
        
        if is_nsfw:
            return random.choice(NSFW_SETTINGS)
        
        # Match settings to niche using expanded arrays
        if any(n in niche_lower for n in ["fitness", "gym", "workout", "health", "training", "exercise"]):
            return random.choice(FITNESS_SETTINGS)
        elif any(n in niche_lower for n in ["fashion", "style", "beauty", "clothing", "outfit", "ootd"]):
            return random.choice(FASHION_SETTINGS)
        elif any(n in niche_lower for n in ["model", "modeling", "photography", "editorial", "photoshoot"]):
            return random.choice(MODELING_SETTINGS)
        elif any(n in niche_lower for n in ["lifestyle", "wellness", "self-care", "mindfulness"]):
            return random.choice(SFW_SETTINGS)  # Use general SFW which includes lifestyle settings
        else:
            return random.choice(SFW_SETTINGS)
    
    async def generate_image_prompt(
        self,
        persona: Persona,
        caption: str,
        platform: str = "instagram",
        content_type: str = "post",
        mood: Optional[str] = None,
    ) -> str:
        """Generate an optimized image prompt using AI.
        
        Args:
            persona: The persona to generate content for
            caption: The caption/topic context for the image
            platform: Target platform (instagram, fanvue, etc.)
            content_type: Type of content (post, story, reel)
            mood: Optional mood/vibe for the image
            
        Returns:
            Optimized prompt string for Higgsfield image generation
        """
        # Select appropriate mood if not provided
        if not mood:
            mood = random.choice(SFW_MOODS)
        
        # Get framing suggestion to avoid body part issues
        framing = self._get_framing_for_content_type(content_type)
        
        # Build the user message with context
        user_content = IMAGE_USER_TEMPLATE.format(
            name=persona.name,
            niche=", ".join(persona.niche),
            appearance_description=self._get_appearance_description(persona),
            platform=platform,
            content_type=content_type,
            caption=caption[:200],  # Truncate long captions
            mood=mood,
            framing_suggestion=framing,
        )
        
        messages = [
            Message(role="system", content=IMAGE_META_PROMPT),
            Message(role="user", content=user_content),
        ]
        
        logger.info(
            "Generating AI image prompt",
            persona=persona.name,
            platform=platform,
            content_type=content_type,
            framing=framing,
        )
        
        result = await self.provider.generate_text(
            messages,
            max_tokens=600,
            temperature=0.8,
        )
        
        prompt = result.text.strip()
        
        logger.info(
            "AI image prompt generated",
            prompt_preview=prompt[:100],
            tokens_used=result.tokens_used,
        )
        
        return prompt
    
    async def generate_video_prompt(
        self,
        persona: Persona,
        speech_phrase: str,
        setting: Optional[str] = None,
        action_description: Optional[str] = None,
        platform: str = "instagram",
        mood: Optional[str] = None,
    ) -> str:
        """Generate an optimized video motion prompt using AI.
        
        Args:
            persona: The persona to generate content for
            speech_phrase: What the subject says (3-5 words max)
            setting: Location/environment for the video
            action_description: What happens in the video
            platform: Target platform
            mood: Optional mood/vibe
            
        Returns:
            Optimized motion prompt string for Higgsfield video generation
        """
        # Select setting if not provided
        if not setting:
            setting = self._select_setting_for_niche(persona.niche)
        
        # Generate follow-up phrase to fill dead space
        followup_phrase = self._get_followup_phrase(speech_phrase)
        
        if not mood:
            mood = random.choice(SFW_MOODS)
        
        # Get voice/accent from persona
        voice_accent = getattr(persona, 'appearance_voice', None) or "American"
        
        user_content = VIDEO_USER_TEMPLATE.format(
            name=persona.name,
            niche=", ".join(persona.niche),
            appearance_description=self._get_appearance_description(persona),
            voice_accent=voice_accent,
            platform=platform,
            setting=setting,
            speech_phrase=speech_phrase,
            followup_phrase=followup_phrase,
            mood=mood,
        )
        
        messages = [
            Message(role="system", content=VIDEO_META_PROMPT),
            Message(role="user", content=user_content),
        ]
        
        logger.info(
            "Generating AI video prompt",
            persona=persona.name,
            speech_phrase=speech_phrase,
            followup_phrase=followup_phrase,
        )
        
        result = await self.provider.generate_text(
            messages,
            max_tokens=700,
            temperature=0.8,
        )
        
        prompt = result.text.strip()
        
        logger.info(
            "AI video prompt generated",
            prompt_preview=prompt[:100],
            tokens_used=result.tokens_used,
        )
        
        return prompt
    
    async def generate_nsfw_image_prompt(
        self,
        persona: Persona,
        setting: Optional[str] = None,
        outfit: Optional[str] = None,
        pose: Optional[str] = None,
        mood: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate an optimized NSFW image prompt using AI.
        
        Args:
            persona: The persona to generate content for
            setting: Location/environment (randomly selected if not provided)
            outfit: What she's wearing (randomly selected if not provided)
            pose: The pose (randomly selected if not provided)
            mood: The mood/vibe (randomly selected if not provided)
            
        Returns:
            Dictionary with prompt and metadata (setting, outfit, pose, mood)
        """
        # Select random elements if not provided
        if not setting:
            setting = random.choice(NSFW_SETTINGS)
        if not outfit:
            outfit = random.choice(NSFW_OUTFITS)
        if not pose:
            pose = random.choice(NSFW_POSES)
        if not mood:
            mood = random.choice(NSFW_MOODS)
        
        user_content = NSFW_IMAGE_USER_TEMPLATE.format(
            name=persona.name,
            appearance_description=self._get_appearance_description(persona),
            setting=setting,
            outfit=outfit,
            pose=pose,
            mood=mood,
        )
        
        messages = [
            Message(role="system", content=NSFW_IMAGE_META_PROMPT),
            Message(role="user", content=user_content),
        ]
        
        logger.info(
            "Generating AI NSFW image prompt",
            persona=persona.name,
            setting=setting,
            mood=mood,
        )
        
        result = await self.provider.generate_text(
            messages,
            max_tokens=700,
            temperature=0.85,
        )
        
        prompt = result.text.strip()
        
        logger.info(
            "AI NSFW image prompt generated",
            prompt_preview=prompt[:100],
            tokens_used=result.tokens_used,
        )
        
        return {
            "prompt": prompt,
            "setting": setting,
            "outfit": outfit,
            "pose": pose,
            "mood": mood,
            "lighting": "natural/ring light",  # For compatibility
        }
    
    async def generate_nsfw_video_prompt(
        self,
        persona: Persona,
        setting: Optional[str] = None,
        outfit: Optional[str] = None,
        motion: Optional[str] = None,
        mood: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate an optimized NSFW video motion prompt using AI.
        
        Args:
            persona: The persona to generate content for
            setting: Location/environment
            outfit: What she's wearing
            motion: The motion/action sequence
            mood: The mood/vibe
            
        Returns:
            Dictionary with prompt and metadata
        """
        # Select random elements if not provided
        if not setting:
            setting = random.choice(NSFW_SETTINGS)
        if not outfit:
            outfit = random.choice(NSFW_OUTFITS)
        if not motion:
            motion = random.choice(NSFW_MOTIONS)
        if not mood:
            mood = random.choice(NSFW_MOODS)
        
        # Get voice/accent from persona
        voice_accent = getattr(persona, 'appearance_voice', None) or "American"
        
        user_content = NSFW_VIDEO_USER_TEMPLATE.format(
            name=persona.name,
            appearance_description=self._get_appearance_description(persona),
            voice_accent=voice_accent,
            setting=setting,
            outfit=outfit,
            motion_description=motion,
            mood=mood,
        )
        
        messages = [
            Message(role="system", content=NSFW_VIDEO_META_PROMPT),
            Message(role="user", content=user_content),
        ]
        
        logger.info(
            "Generating AI NSFW video prompt",
            persona=persona.name,
            setting=setting,
            mood=mood,
        )
        
        result = await self.provider.generate_text(
            messages,
            max_tokens=800,
            temperature=0.85,
        )
        
        prompt = result.text.strip()
        
        logger.info(
            "AI NSFW video prompt generated",
            prompt_preview=prompt[:100],
            tokens_used=result.tokens_used,
        )
        
        return {
            "prompt": prompt,
            "setting": setting,
            "outfit": outfit,
            "motion": motion,
            "mood": mood,
        }


# Singleton instance for convenience
_generator: Optional[AIPromptGenerator] = None


def get_prompt_generator() -> AIPromptGenerator:
    """Get or create the prompt generator instance."""
    global _generator
    if _generator is None:
        _generator = AIPromptGenerator()
    return _generator
