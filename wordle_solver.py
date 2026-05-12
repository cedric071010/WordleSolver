from collections import Counter


known_green = {}

def reset_possible_words():
    with open("valid_words.txt", "r") as valid_file:
        words = valid_file.read()

    with open("possible_words.txt", "w") as possible_file:
        possible_file.write(words)


def count_letters():
    counts = Counter()

    with open("possible_words.txt", "r") as file:
        words = [line.strip() for line in file if line.strip()]

    for word in words:
        letter_count = Counter(word)

        for letter, amount in letter_count.items():
            counts[letter] += 1
            if amount >= 2:
                counts[f"{letter}2"] += 1
            if amount >= 3:
                counts[f"{letter}3"] += 1
            if amount >= 4:
                counts[f"{letter}4"] += 1
            if amount >= 5:
                counts[f"{letter}5"] += 1

    return counts


def score_word(word, letter_data):

    score = 0
    letter_count = Counter(word)

    for letter, amount in letter_count.items():

        score += letter_data[letter]
        if amount >= 2:
            score += letter_data[f"{letter}2"]
        if amount >= 3:
            score += letter_data[f"{letter}3"]
        if amount >= 4:
            score += letter_data[f"{letter}4"]
        if amount >= 5:
            score += letter_data[f"{letter}5"]

    return score


def get_letters_from_input(text):
    text = text.replace(" ", "").lower()
    return [char for char in text if char.isalpha()]


def get_user_rules():
    green = known_green.copy()
    yellow = {}
    gray = set()

    print("\n=== GREEN LETTERS ===")

    for i in range(5):

        if i in known_green:
            print(f"Green at position {i + 1}: {known_green[i]} already known")
            continue

        while True:
            letter = input(f"Green at position {i + 1}: ").strip().lower()

            if not letter:
                break

            if len(letter) == 1 and letter.isalpha():
                green[i] = letter
                known_green[i] = letter
                break

            print("Invalid. Enter one letter only, or press Enter.")

    print("\n=== YELLOW LETTERS ===")

    for i in range(5):
        yellow[i] = []

        text = input(f"Yellow at position {i + 1}: ").strip().lower()

        if text:
            yellow[i] = get_letters_from_input(text)

    print("\n=== GRAY LETTERS ===")

    gray_input = input("Gray letters: ").strip().lower()

    for letter in get_letters_from_input(gray_input):
        gray.add(letter)

    return green, yellow, gray


def is_possible_word(word, green, yellow, gray):

    word_count = Counter(word)
    confirmed_count = Counter()

    for letter in green.values():
        confirmed_count[letter] += 1

    for letters in yellow.values():
        for letter in letters:
            confirmed_count[letter] += 1

    for position, letter in green.items():
        if word[position] != letter:
            return False

    for position, letters in yellow.items():
        for letter in letters:
            if word[position] == letter:
                return False

    for letter, amount in confirmed_count.items():
        if word_count[letter] < amount:
            return False

    for letter in gray:
        if confirmed_count[letter] == 0:
            if letter in word:
                return False
        else:
            if word_count[letter] > confirmed_count[letter]:
                return False

    return True


def update_possible_words():

    green, yellow, gray = get_user_rules()

    with open("possible_words.txt", "r") as file:
        words = [line.strip().lower() for line in file if line.strip()]

    possible_words = []

    for word in words:
        if is_possible_word(word, green, yellow, gray):
            possible_words.append(word)

    with open("possible_words.txt", "w") as file:
        for word in possible_words:
            file.write(word + "\n")

    if len(possible_words) == 0:
        print("\nWARNING: 0 possible words left.")

    else:
        print(f"\nPossible words left: {len(possible_words)}")

    if len(possible_words) <= 25:
        print(possible_words)

    letter_data = count_letters()
    """
    print("\n=== LETTER COUNTS ===")
    print(letter_data)
    """
    print("\n=== WORD SCORES ===")

    scored_words = []

    for word in possible_words:
        score = score_word(word, letter_data)
        scored_words.append((word, score))

    scored_words.sort(key=lambda x: x[1], reverse=True)

    for word, score in scored_words[:5]:
        print(word, score)

    if scored_words:
        print(f"\nBEST WORD: {scored_words[0][0]}")


if __name__ == "__main__":

    reset_possible_words()

    letter_data = count_letters()

    with open("possible_words.txt", "r") as file:
        words = [line.strip().lower() for line in file if line.strip()]

    scored_words = []

    for word in words:
        score = score_word(word, letter_data)
        scored_words.append((word, score))

    scored_words.sort(key=lambda x: x[1], reverse=True)

    print("\n=== STARTING BEST WORD ===")
    print(scored_words[0][0], scored_words[0][1])

    while True:
    
        update_possible_words()
    
        with open("possible_words.txt", "r") as file:
            remaining_words = [
                line.strip().lower()
                for line in file
                if line.strip()
            ]

        if len(remaining_words) == 1:
            print(f"\nANSWER: {remaining_words[0]}")
            break
    
        action = input("\nEnter r to reset, q to quit, anything else to continue: ").strip().lower()
    
        if action == "q":
            break
    
        if action == "r":
            reset_possible_words()
            known_green.clear()
            print("\nReset done.")