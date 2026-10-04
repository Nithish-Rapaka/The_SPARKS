from automation.ai.image_provider import generate_image


image_path = generate_image(
    user_requirement=(
        "A modern futuristic office where humans and AI robots "
        "are collaborating on software development"
    ),
    linkedin_post=(
        "Artificial intelligence is changing the way software teams "
        "build products."
    ),
)

print("IMAGE CREATED:")
print(image_path)