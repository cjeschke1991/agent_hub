"""Curated tips for people living with Tourette syndrome, organised by category.

Each category is a dict with:
  id       : str   — unique slug
  label    : str   — display name
  icon     : str   — emoji for the tab/header
  color    : str   — hex accent used in the UI card border
  intro    : str   — one-sentence context for the category
  tips     : list[dict]
    title  : str   — short headline for the tip
    body   : str   — 1-3 sentence explanation
"""
from __future__ import annotations

CATEGORIES: list[dict] = [
    {
        "id": "managing_tics",
        "label": "Managing Tics",
        "icon": "🧠",
        "color": "#6C63FF",
        "intro": "Practical strategies to reduce tic frequency, intensity, and interference in daily life.",
        "tips": [
            {
                "title": "Identify your personal tic triggers",
                "body": (
                    "Common triggers include stress, excitement, caffeine, fatigue, and screen time. "
                    "Keep a simple log for a week — noting time of day, activity, and tic intensity — "
                    "to spot your personal patterns and adjust accordingly."
                ),
            },
            {
                "title": "Use Comprehensive Behavioral Intervention for Tics (CBIT)",
                "body": (
                    "CBIT is the gold-standard, non-medication therapy for TS. "
                    "A therapist teaches you to notice the 'urge' before a tic and redirect "
                    "it into a competing behavior that is less noticeable. "
                    "Clinical trials show CBIT reduces tic severity in roughly two-thirds of participants."
                ),
            },
            {
                "title": "Leverage the 'tic-free window' — distraction and flow",
                "body": (
                    "Many people notice tics diminish when fully absorbed in an activity "
                    "(sport, music, gaming, reading). Build in daily 'flow' time as a natural suppression period. "
                    "This is not avoidance — it is neurologically grounded stress relief."
                ),
            },
            {
                "title": "Schedule a private 'release' time",
                "body": (
                    "Suppressing tics in public takes real mental energy. "
                    "Give yourself a few minutes of private time each day to let tics happen freely "
                    "without judgment. This 'release' period reduces build-up and overall fatigue."
                ),
            },
            {
                "title": "Prioritise consistent sleep",
                "body": (
                    "Sleep deprivation is one of the most reliable tic amplifiers. "
                    "Aim for 8–9 hours on a consistent schedule. Even shifting bedtime 30 minutes earlier "
                    "can measurably reduce tic frequency the next day for many people."
                ),
            },
            {
                "title": "Discuss medication options with a specialist",
                "body": (
                    "Medications (alpha-2 agonists like guanfacine/clonidine, or antipsychotics for severe cases) "
                    "can be very effective when CBIT alone is insufficient. "
                    "Consult a movement disorder neurologist or TS-specialised psychiatrist — "
                    "not just a general practitioner — for the most up-to-date options."
                ),
            },
        ],
    },
    {
        "id": "school_work",
        "label": "School & Work",
        "icon": "🎓",
        "color": "#43AA8B",
        "intro": "How to thrive academically and professionally while managing TS in structured environments.",
        "tips": [
            {
                "title": "Request formal accommodations early",
                "body": (
                    "In the US, students with TS are protected under IDEA and Section 504. "
                    "Common accommodations include extended test time, a quiet testing room, "
                    "permission to leave class briefly, and oral exam options. "
                    "Request an IEP or 504 Plan as soon as possible — early documentation matters."
                ),
            },
            {
                "title": "Tell one trusted person at school or work",
                "body": (
                    "You do not need to disclose to everyone, but having one ally "
                    "(a teacher, supervisor, or HR contact) who understands TS can defuse "
                    "misunderstandings before they escalate. Brief, factual explanations "
                    "('I have a neurological condition — my movements are involuntary') are usually sufficient."
                ),
            },
            {
                "title": "Sit strategically in the classroom or meeting room",
                "body": (
                    "A seat near the back or side wall reduces the feeling of being observed, "
                    "which itself lowers anxiety and often reduces tic frequency. "
                    "Near an exit is also helpful if you need a quick 'tic break' in the hall."
                ),
            },
            {
                "title": "Leverage written or asynchronous formats when possible",
                "body": (
                    "If vocal tics interfere with oral presentations, ask whether written reports, "
                    "recorded video submissions, or one-on-one presentations to the instructor "
                    "are acceptable alternatives. Most educators and managers will accommodate this readily."
                ),
            },
            {
                "title": "Use noise-cancelling headphones for focus tasks",
                "body": (
                    "Many people with TS also have ADHD or sensory sensitivities. "
                    "Headphones signal 'do not disturb,' reduce ambient distraction, "
                    "and can help you enter a focus state where tics naturally decrease."
                ),
            },
        ],
    },
    {
        "id": "social",
        "label": "Social Situations",
        "icon": "🤝",
        "color": "#F8961E",
        "intro": "Navigating friendships, dating, and public life with confidence.",
        "tips": [
            {
                "title": "Prepare a short, calm explanation",
                "body": (
                    "Having a rehearsed 1-2 sentence explanation removes the anxiety of being caught off-guard. "
                    "Something like: 'I have Tourette syndrome — my movements and sounds are involuntary, "
                    "kind of like a neurological hiccup. I'm totally fine.' "
                    "Saying it casually signals that it is not a big deal."
                ),
            },
            {
                "title": "Disclose on your own terms and timeline",
                "body": (
                    "You are never obligated to explain your tics to anyone. "
                    "On dates or with new friends, waiting until there is a natural opening "
                    "— rather than disclosing immediately — often leads to more comfortable conversations. "
                    "Most people respond with curiosity, not rejection."
                ),
            },
            {
                "title": "Choose lower-stimulation environments when you need a reset",
                "body": (
                    "Loud, crowded, or high-energy environments (concerts, parties, sports events) "
                    "can amplify tics significantly. It is not avoidance to step outside briefly, "
                    "find a quiet corner, or leave early — it is self-regulation."
                ),
            },
            {
                "title": "Educate, don't apologise",
                "body": (
                    "Constant apologies for tics inadvertently signal shame. "
                    "When tics are noticed, a brief matter-of-fact explanation is more powerful "
                    "than an apology. 'That's my Tourette's' said confidently changes the dynamic "
                    "far more effectively than 'I'm so sorry.'"
                ),
            },
            {
                "title": "Find community — online and in person",
                "body": (
                    "The Tourette Association of America, TikTok's #TouretteSyndrome community, "
                    "and Reddit's r/Tourettes are full of people sharing strategies and support. "
                    "Meeting even one other person with TS can be profoundly validating "
                    "and reduce the sense of isolation that many people feel."
                ),
            },
        ],
    },
    {
        "id": "mental_health",
        "label": "Mental Health & Wellbeing",
        "icon": "💚",
        "color": "#90BE6D",
        "intro": "TS frequently co-occurs with anxiety, OCD, and ADHD — caring for your whole mind matters.",
        "tips": [
            {
                "title": "Treat co-occurring conditions with equal seriousness",
                "body": (
                    "Up to 86% of people with TS have at least one co-occurring condition: "
                    "ADHD (~60%), OCD (~50%), anxiety, or depression. "
                    "For many people, addressing these co-occurring conditions improves quality of life "
                    "more than any tic-focused treatment. Seek evaluation for all of them."
                ),
            },
            {
                "title": "Separate your identity from your tics",
                "body": (
                    "TS is something you have, not something you are. "
                    "Cognitive-behavioral therapy (CBT) can help challenge thoughts like "
                    "'I'm broken' or 'people think I'm weird' and replace them with more accurate beliefs. "
                    "Many people report that this mindset shift is the single most impactful change they make."
                ),
            },
            {
                "title": "Exercise regularly — it directly reduces tic severity",
                "body": (
                    "Multiple studies show that aerobic exercise reduces tic frequency and severity "
                    "in the hours following a workout. Even 20-30 minutes of brisk walking, swimming, "
                    "or cycling produces measurable effects. It also combats the anxiety that amplifies tics."
                ),
            },
            {
                "title": "Practice mindfulness — but do it right for TS",
                "body": (
                    "Standard mindfulness can increase tic awareness and temporarily worsen tics "
                    "for some people. Instead, try 'urge surfing' — observing the pre-tic urge "
                    "without judgment and letting it pass. This is specifically adapted for TS "
                    "and is a core component of CBIT."
                ),
            },
            {
                "title": "Don't wait for a crisis to seek support",
                "body": (
                    "Many people with TS only see a therapist when things get very bad. "
                    "Regular check-ins with a TS-informed therapist — even quarterly — "
                    "build coping skills proactively and prevent the anxiety spiral "
                    "that makes tics significantly worse."
                ),
            },
        ],
    },
    {
        "id": "disclosure",
        "label": "Disclosure & Advocacy",
        "icon": "📣",
        "color": "#577590",
        "intro": "When, how, and why to share your diagnosis — and how to advocate for yourself.",
        "tips": [
            {
                "title": "Know your rights — TS is a protected disability",
                "body": (
                    "In the US, TS qualifies as a disability under the ADA, Section 504, and IDEA. "
                    "This means employers and schools are legally required to provide reasonable accommodations. "
                    "You do not need to disclose the exact diagnosis — 'neurological condition' is sufficient "
                    "for most workplace accommodation requests."
                ),
            },
            {
                "title": "Use the 'iceberg' explanation when educating others",
                "body": (
                    "Most people only see the tics — the visible tip. "
                    "Explaining that TS often comes with a below-the-surface iceberg "
                    "(sensory urges, OCD tendencies, ADHD, anxiety) helps others understand "
                    "why it affects more than just movements."
                ),
            },
            {
                "title": "Correct misrepresentations calmly and factually",
                "body": (
                    "The media stereotype of TS as 'uncontrollable swearing' (coprolalia) affects "
                    "only about 10-15% of people with TS. When you hear this trope, "
                    "a calm correction ('Actually, only about 1 in 10 people with TS experience that') "
                    "is one of the most effective forms of public advocacy."
                ),
            },
            {
                "title": "Document everything when seeking accommodations",
                "body": (
                    "Keep a file with your diagnosis letter, any neurologist or psychiatrist notes, "
                    "and records of accommodation requests and responses. "
                    "This is essential if you ever need to escalate a denied accommodation "
                    "at school or work."
                ),
            },
            {
                "title": "Sharing your story has outsized impact",
                "body": (
                    "Public figures like Billie Eilish and Tim Howard have shown that "
                    "one candid disclosure reaches millions. Even at a personal scale, "
                    "sharing your experience with one person in your community can change "
                    "how they treat the next person they meet with TS."
                ),
            },
        ],
    },
    {
        "id": "parents_caregivers",
        "label": "For Parents & Caregivers",
        "icon": "👨‍👩‍👧",
        "color": "#F94144",
        "intro": "Supporting a child or loved one with TS — practical and emotional guidance.",
        "tips": [
            {
                "title": "Never ask your child to stop ticcing",
                "body": (
                    "Asking a child to suppress tics — even gently — increases anxiety, "
                    "builds shame, and typically makes tics worse. "
                    "Instead, create an environment where tics are acknowledged neutrally: "
                    "'I see your tics are more active today — want to talk about what's on your mind?'"
                ),
            },
            {
                "title": "Educate teachers proactively, every school year",
                "body": (
                    "Teachers change. Even with a 504 Plan, personally meeting with each new teacher "
                    "at the start of the year — with a one-page TS summary — dramatically improves "
                    "classroom experiences and reduces incidents of being disciplined for tics."
                ),
            },
            {
                "title": "Watch for the emotional toll, not just the tics",
                "body": (
                    "Children with TS are significantly more likely to experience bullying, "
                    "social rejection, and low self-esteem. Ask regularly about friendships and feelings, "
                    "not just tic frequency. A child who feels understood at home can withstand "
                    "a great deal more at school."
                ),
            },
            {
                "title": "Connect with the Tourette Association of America",
                "body": (
                    "The TAA (tourette.org) offers school educator kits, a national network of "
                    "support groups, a healthcare provider directory, and a summer camp program (TSA-Camp) "
                    "where children with TS meet peers, often for the first time. "
                    "These peer connections are transformative."
                ),
            },
            {
                "title": "Take care of yourself too",
                "body": (
                    "Parenting a child with TS, especially with co-occurring ADHD or OCD, "
                    "is genuinely exhausting. Parent support groups (in-person and online) "
                    "are not a luxury — they are a necessity. "
                    "Your wellbeing directly affects your child's wellbeing."
                ),
            },
        ],
    },
    {
        "id": "lifestyle",
        "label": "Lifestyle & Daily Habits",
        "icon": "🌱",
        "color": "#F9C74F",
        "intro": "Day-to-day habits that measurably improve tic management and overall quality of life.",
        "tips": [
            {
                "title": "Reduce caffeine, especially in the afternoon",
                "body": (
                    "Caffeine is a stimulant that elevates anxiety and directly worsens tics in many people. "
                    "Try cutting caffeine after noon for two weeks and track your tic log. "
                    "Many people notice a meaningful improvement without changing anything else."
                ),
            },
            {
                "title": "Maintain a consistent daily routine",
                "body": (
                    "Unpredictability and transitions are significant tic triggers for many people with TS. "
                    "A predictable daily schedule — consistent wake time, meal times, and wind-down routine — "
                    "reduces the ambient anxiety that amplifies tics."
                ),
            },
            {
                "title": "Try magnesium supplementation (with doctor approval)",
                "body": (
                    "Several small studies and a large body of anecdotal evidence suggest "
                    "magnesium glycinate (200-400mg/day) may reduce tic severity. "
                    "It is low-risk, inexpensive, and worth discussing with your doctor. "
                    "It also supports sleep quality."
                ),
            },
            {
                "title": "Build a physical activity habit that you enjoy",
                "body": (
                    "The key word is 'enjoy.' Forced, joyless exercise does not produce "
                    "the same neurological benefits. Martial arts, swimming, rock climbing, "
                    "and team sports are popular among people with TS because they combine "
                    "the benefits of exercise, focus, and social connection."
                ),
            },
            {
                "title": "Design your environment to reduce sensory overload",
                "body": (
                    "Bright flickering lights, loud background noise, and physical discomfort "
                    "(scratchy clothing tags, tight collars) are all common tic amplifiers. "
                    "Small environmental adjustments — dimmer lighting, softer clothing, "
                    "noise-cancelling headphones — add up to meaningful daily relief."
                ),
            },
        ],
    },
    {
        "id": "medical",
        "label": "Medical & Treatment",
        "icon": "🏥",
        "color": "#277DA1",
        "intro": "Understanding your treatment options and how to get the best care.",
        "tips": [
            {
                "title": "Seek a TS specialist, not just a general neurologist",
                "body": (
                    "Movement disorder neurologists and child psychiatrists who specialise in TS "
                    "are significantly more effective than general practitioners. "
                    "The Tourette Association of America maintains a searchable directory of "
                    "TS-trained healthcare providers at tourette.org/find-a-doctor."
                ),
            },
            {
                "title": "Understand the CBIT vs medication decision",
                "body": (
                    "Current guidelines recommend CBIT as the first-line treatment for most people. "
                    "Medication is typically added when tics are severe, when CBIT is inaccessible, "
                    "or when co-occurring conditions (ADHD, OCD) also need pharmaceutical management. "
                    "The decision is highly individual — work with a specialist."
                ),
            },
            {
                "title": "Track tics systematically with the Yale Global Tic Severity Scale (YGTSS)",
                "body": (
                    "The YGTSS is the standard clinical tool for measuring tic severity over time. "
                    "Using it at home monthly gives you objective data to bring to appointments, "
                    "helping your doctor make evidence-based decisions rather than relying solely "
                    "on recalled impressions."
                ),
            },
            {
                "title": "Ask about Deep Brain Stimulation (DBS) for severe adult cases",
                "body": (
                    "DBS is an FDA-approved treatment for severe, treatment-refractory adult TS. "
                    "It is not right for most people, but for those with severe, disabling tics "
                    "that have not responded to other treatments, it can be life-changing. "
                    "It is only available at specialized centers."
                ),
            },
            {
                "title": "Prepare a 'TS passport' for medical appointments",
                "body": (
                    "Bring a one-page document to every appointment listing: your current medications "
                    "and doses, co-occurring diagnoses, past treatments tried and outcomes, "
                    "and your top 2-3 current concerns. This ensures nothing is forgotten "
                    "in the limited time of a medical visit."
                ),
            },
        ],
    },
]
