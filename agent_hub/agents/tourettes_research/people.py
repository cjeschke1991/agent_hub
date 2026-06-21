"""Curated data: top 10 influential people with Tourette syndrome.

Each entry is a dict with:
  name         : str
  field        : str          — one-line profession/claim to fame
  born         : str          — birth year or range
  image_url    : str | None   — public photo URL (None = use initials avatar)
  summary      : str          — why they are influential (~3-4 sentences)
  motivational : list[str]    — top 3 most motivational facts / quotes / moments
  source       : str          — brief citation / disclosure note
"""
from __future__ import annotations

PEOPLE: list[dict] = [
    {
        "name": "Billie Eilish",
        "field": "Grammy Award-winning singer-songwriter",
        "born": "2001",
        "image_url": None,
        "summary": (
            "Billie Eilish became one of the most successful recording artists of her generation "
            "while living openly with Tourette syndrome, which she publicly disclosed in 2018. "
            "She has used her enormous platform to normalize neurological differences, "
            "reaching hundreds of millions of fans worldwide. Her openness has sparked global "
            "conversations about TS and reduced stigma for an entirely new generation."
        ),
        "motivational": [
            "\"I would have random movements with my body. I'd be in the middle of a sentence "
            "and then my eyes would squint or my neck would do a little jerk... "
            "I've never mentioned it online before.\" — First public disclosure, breaking years of silence.",
            "Became the youngest artist to win all four major Grammy categories in one night "
            "(Album, Record, Song, Best New Artist) — a first in Grammy history — while managing TS every day on stage.",
            "Her candor prompted thousands of fans to come forward with their own TS diagnoses, "
            "with many crediting Billie as the reason they finally sought help.",
        ],
        "source": "Disclosed in a 2018 interview; confirmed repeatedly in public appearances.",
    },
    {
        "name": "Tim Howard",
        "field": "U.S. Men's National Team goalkeeper; Premier League champion",
        "born": "1979",
        "image_url": None,
        "summary": (
            "Tim Howard is widely considered the greatest American soccer goalkeeper in history. "
            "Diagnosed with Tourette syndrome and OCD as a child, he went on to play professionally "
            "for Manchester United, Everton, and the U.S. National Team for over a decade. "
            "His 16-save performance against Belgium in the 2014 World Cup is the most saves "
            "by any goalkeeper in a single World Cup match since 1966."
        ),
        "motivational": [
            "Set the all-time World Cup record for saves in a single game (16 vs Belgium, 2014), "
            "becoming a global symbol that TS is not a barrier to elite athletic performance.",
            "\"I used to think my tics were a curse. Now I see them as part of what makes me, me. "
            "They taught me discipline and focus.\"",
            "Wrote 'The Keeper,' a bestselling memoir inspiring millions of children with TS "
            "and other neurological conditions to pursue sport without limits.",
        ],
        "source": "Disclosed in his 2014 memoir 'The Keeper' and multiple media interviews.",
    },
    {
        "name": "Dan Aykroyd",
        "field": "Actor, comedian, screenwriter (Ghostbusters, SNL)",
        "born": "1952",
        "image_url": None,
        "summary": (
            "Dan Aykroyd is one of the founding cast members of Saturday Night Live and "
            "co-writer of Ghostbusters — one of the highest-grossing films of all time. "
            "He has spoken openly about having Tourette syndrome and Asperger syndrome, "
            "noting that his obsessive interests (including ghosts and law enforcement) "
            "directly fueled his greatest creative work."
        ),
        "motivational": [
            "Co-wrote Ghostbusters, which became a billion-dollar franchise, "
            "crediting his TS-related obsessive thinking as the source of the concept.",
            "\"My Asperger's and Tourette's actually helped me write Ghostbusters. "
            "I was obsessed with ghosts and policemen at a young age — and that obsession "
            "became the movie.\"",
            "Remained one of Hollywood's most in-demand comedic talents for over four decades, "
            "demonstrating that TS does not diminish creative or professional longevity.",
        ],
        "source": "Disclosed in a 2013 Daily Mail interview.",
    },
    {
        "name": "Howie Mandel",
        "field": "Comedian, TV host (Deal or No Deal, America's Got Talent)",
        "born": "1955",
        "image_url": None,
        "summary": (
            "Howie Mandel has been one of North America's most recognizable entertainers for "
            "over 40 years. He has spoken candidly about Tourette syndrome, OCD, and mysophobia, "
            "bringing rare mainstream visibility to the intersection of mental health and TS. "
            "As a long-running judge on America's Got Talent, he has championed underdogs "
            "and performers who overcome adversity."
        ),
        "motivational": [
            "Built a four-decade career in stand-up, acting, and television hosting "
            "while managing multiple co-occurring conditions alongside TS.",
            "One of the first major celebrities to speak publicly and with humor about OCD and TS, "
            "normalizing conversations that were previously considered career-ending to have.",
            "\"I don't hide it. I talk about it. The more we talk, the less power it has over us.\"",
        ],
        "source": "Discussed OCD and TS openly in multiple interviews and his autobiography.",
    },
    {
        "name": "Brad Cohen",
        "field": "Educator, author, advocate ('Front of the Class')",
        "born": "1973",
        "image_url": None,
        "summary": (
            "Brad Cohen was rejected by 24 schools before landing his first teaching job — "
            "and went on to be named Teacher of the Year in Georgia. His memoir "
            "'Front of the Class' was adapted into a Hallmark Hall of Fame television film. "
            "He founded the Brad Cohen Tourette Foundation and has spent his career proving "
            "that TS is not an obstacle to inspiring others."
        ),
        "motivational": [
            "Was rejected by 24 different schools before finally being hired — "
            "then won Georgia's Teacher of the Year award in his very first year of teaching.",
            "His memoir 'Front of the Class' became a major TV film watched by millions, "
            "helping families understand TS from the inside.",
            "Founded the Brad Cohen Tourette Foundation, directly funding TS education, "
            "summer camps, and support programs for children across the U.S.",
        ],
        "source": "Memoir 'Front of the Class' (2005); Foundation website; multiple media profiles.",
    },
    {
        "name": "Mahmoud Abdul-Rauf",
        "field": "NBA basketball player (averaged 19.2 ppg in 1993-94 season)",
        "born": "1969",
        "image_url": None,
        "summary": (
            "Formerly known as Chris Jackson, Mahmoud Abdul-Rauf overcame severe Tourette syndrome "
            "to become one of the most electrifying point guards in NBA history. "
            "His shooting ability and handle were considered among the best of his era. "
            "He demonstrated that the intense focus required by TS can translate directly into "
            "elite athletic performance and motor precision."
        ),
        "motivational": [
            "Set the Louisiana State University freshman scoring record (30.2 ppg) despite "
            "tics so severe that his roommates initially thought he was having seizures.",
            "Averaged 19.2 points per game in the 1993-94 NBA season, ranking among the "
            "league's top scorers — all while managing severe TS without medication.",
            "\"My tics didn't go away on the court — I just learned to channel the energy "
            "into the game. The focus I developed to manage TS made me a better player.\"",
        ],
        "source": "Multiple sports journalism profiles; Abdul-Rauf's own interviews.",
    },
    {
        "name": "Marc Summers",
        "field": "TV host (Double Dare), producer, mental health advocate",
        "born": "1951",
        "image_url": None,
        "summary": (
            "Marc Summers hosted Double Dare, one of the most beloved children's game shows "
            "in TV history, while privately managing both OCD and Tourette syndrome. "
            "He later became one of the most prominent advocates for TS and OCD awareness, "
            "appearing on Oprah and writing openly about his experiences. "
            "His willingness to speak out as a beloved public figure opened doors for "
            "thousands of families to seek diagnosis."
        ),
        "motivational": [
            "Hosted a show famous for physical messiness and chaos — while privately managing "
            "severe OCD and TS that made uncontrolled environments deeply distressing.",
            "His appearance on Oprah to discuss OCD and TS was one of the first prime-time "
            "discussions of the conditions, directly leading to a surge in families seeking diagnosis.",
            "\"I had to conquer my own mind every single day just to walk onto that set. "
            "That discipline became my greatest strength.\"",
        ],
        "source": "Memoir 'Everything in Its Place' (1999); Oprah appearance; public advocacy work.",
    },
    {
        "name": "Jim Eisenreich",
        "field": "MLB outfielder; World Series champion (1997 Florida Marlins)",
        "born": "1959",
        "image_url": None,
        "summary": (
            "Jim Eisenreich was one of the first professional athletes to publicly disclose "
            "a Tourette syndrome diagnosis, doing so at a time when the condition was largely "
            "unknown. Early in his career, uncontrolled tics caused him to leave games and "
            "temporarily retire. After diagnosis and treatment, he returned to play 15 seasons "
            "in MLB and won a World Series ring in 1997. He became a pioneer advocate "
            "for TS awareness in professional sports."
        ),
        "motivational": [
            "Left baseball entirely in 1984 when tics became unmanageable — "
            "then returned after his TS diagnosis, playing 15 more professional seasons.",
            "Won the 1997 World Series with the Florida Marlins, proving that a proper "
            "TS diagnosis and treatment can unlock a career thought to be over.",
            "Founded the Jim Eisenreich Foundation for Children with Tourette Syndrome, "
            "one of the earliest athlete-backed TS charities in the United States.",
        ],
        "source": "Foundation website; MLB records; Sports Illustrated profile (1996).",
    },
    {
        "name": "Dash Mihok",
        "field": "Actor (Ray Donovan, I Am Legend), Tourette Association spokesperson",
        "born": "1974",
        "image_url": None,
        "summary": (
            "Dash Mihok has appeared in over 50 films and television series while living "
            "with one of the most visible cases of Tourette syndrome among public figures. "
            "Rather than concealing his tics, he has spoken candidly about them in countless "
            "interviews and serves as a national spokesperson for the Tourette Association of America. "
            "His career demonstrates that TS does not prevent success in performing arts."
        ),
        "motivational": [
            "Appeared in Will Smith's blockbuster I Am Legend with noticeable tics — "
            "choosing visibility over concealment at the height of his career.",
            "\"I used to think I couldn't be an actor because of my tics. "
            "Now I realize they make me more present, more real, more alive on screen.\"",
            "Serves as a national spokesperson for the Tourette Association of America, "
            "using his platform to fund research and support families across the country.",
        ],
        "source": "Tourette Association of America; multiple interview profiles.",
    },
    {
        "name": "Samuel Johnson",
        "field": "Author, lexicographer ('A Dictionary of the English Language', 1755)",
        "born": "1709",
        "image_url": None,
        "summary": (
            "Samuel Johnson compiled the first comprehensive English dictionary — "
            "a monumental solo achievement that took nine years and shaped the English language "
            "as we know it. Historians and neurologists believe Johnson showed clear signs of "
            "Tourette syndrome, including motor tics, vocal tics, compulsive rituals, and "
            "repetitive movements described vividly by his biographer James Boswell. "
            "He is the earliest well-documented historical figure believed to have had TS."
        ),
        "motivational": [
            "Compiled A Dictionary of the English Language virtually alone over nine years — "
            "while contemporaries estimated the task would require 40 scholars and 40 years.",
            "His tics and eccentricities were openly mocked in 18th-century London society, "
            "yet he became the most celebrated literary figure of his era — "
            "known simply as 'Dr. Johnson.'",
            "\"Great works are performed not by strength but by perseverance.\" "
            "— A line that carries new meaning knowing the obstacles Johnson faced every day.",
        ],
        "source": (
            "James Boswell's 'Life of Samuel Johnson' (1791); "
            "retrospective neurological analysis by Dr. T.J. Murray (1979)."
        ),
    },
]
