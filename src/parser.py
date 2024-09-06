import fitz

def extract_words_with_fonts(file_bytes):
    doc = fitz.open(stream=file_bytes)
    words_with_fonts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        
        for block in blocks:
            if block['type'] == 0:  # text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span['text'].strip()
                        font = span['font']
                        size = span['size']
                        words = text.split()  # Split the span text into individual words
                        
                        for word in words:
                            words_with_fonts.append({
                                'word': word,
                                'font': font,
                                'size': size,
                                'page_num': page_num + 1  # page numbers are 1-indexed
                            })

    return words_with_fonts


def is_header(word):
    # Heuristic to determine if a block is a header
    if word['font'] == 'CIDFont+F2':
        return word
    else:
        return None

headers = ['Diagnosen', 
            'Weitere Diagnosen', 
            'Vordiagnosen', 
            'Anamnese',
            'Klinische Befunde',
            'Laborwerte',
            'Befunde',
            'Weitere Befunde',
            'Verlauf',
            'Procedere',
            'Medikation',
            'Entlassmedikation']



double_headers_first = ['Weitere', 'Klinische']
double_headers_second = ['Diagnosen', 'Befunde']
   

def extract_sections(text_blocks):

    position_of_headers = {
        'Diagnosen': 0,
        'Weitere Diagnosen': 0,
        'Vordiagnosen': 0,
        'Anamnese': 0,
        'Klinische Befunde': 0,
        'Laborwerte': 0,
        'Befunde': 0,
        'Weitere Befunde': 0,
        'Verlauf': 0,
        'Procedere': 0,
        'Medikation': 0,
        'Entlassmedikation': 0
    }

    sections = {header: '' for header in headers}
    
    current_header = None
    last_word = None
    ignore_next = False
    
    counter = 0
    for block in text_blocks:
        word = block['word']
        
        try:
            text_blocks[counter + 1]['word']
        except IndexError:
            pass
        
        if is_header(block):
            # Check if the word contains a double point
            if word.endswith(':'):
                word = word[:-1].strip()
            
            if word in double_headers_first:
                try:
                    second_word = text_blocks[counter + 1]['word']
                except IndexError:
                    second_word = "random_word"

                if second_word in double_headers_second:
                    current_header = f"{word} {second_word}"
                    position_of_headers[current_header] = counter
                    ignore_next = True


            elif word in headers:
                if ignore_next:
                    ignore_next = False
                else:
                    current_header = word
                    position_of_headers[current_header] = counter

        counter += 1
    
    ##### now extract the sections using the positions
    # Filter out headers with a position of 0
    filtered_headers = {k: v for k, v in position_of_headers.items() if v > 0}

    # Sort headers by their positions
    sorted_headers = sorted(filtered_headers.items(), key=lambda item: item[1])

    # Extract text sections based on header positions
    for i, (header, start_pos) in enumerate(sorted_headers):
        if i + 1 < len(sorted_headers):
            end_pos = sorted_headers[i + 1][1]
        else:
            end_pos = len(text_blocks)

        # Combine words to form the text segment
        text_segment = ' '.join([block['word'] for block in text_blocks[start_pos:end_pos]]).strip()
        sections[header] = text_segment

    return sections

def get_pdf_sections(file_bytes):
    text_blocks = extract_words_with_fonts(file_bytes)

    sections = {}

    if text_blocks:
        sections = extract_sections(text_blocks)
                    
    return sections
