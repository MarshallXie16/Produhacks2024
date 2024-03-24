from openai import OpenAI

OPENAI_API_KEY = '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'
client = OpenAI(api_key=OPENAI_API_KEY)

@app.route('/submit', methods=['GET'])
def submit():
    if request.method == 'GET':
        # Get the form data
        completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a poetic assistant, skilled in explaining complex programming concepts with creative flair."},
            {"role": "user", "content": "Compose a poem that explains the concept of recursion in programming."}
        ]
        )

        print(completion.choices[0].message)

        # Return the result to the user
        return 'ur mum'