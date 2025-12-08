SET search_path TO content, public;

INSERT INTO film_work (id, title, description, rating, created_at, updated_at)
VALUES
  (
    'aae5751a-865f-4724-9db9-26cafee54e34',
    'Star Wars: Episode IV - A New Hope',
    'A classic space opera about Luke Skywalker, the Rebel Alliance and the battle against the Galactic Empire.',
    8.6,
    NOW(),
    NOW()
  ),
  (
    '0c834d17-f6a4-472b-a5b0-e6e856c96b55',
    'Star Wars: Episode V - The Empire Strikes Back',
    'The Empire strikes back against the Rebels while Luke seeks Jedi training from Yoda.',
    8.7,
    NOW(),
    NOW()
  ),
  (
    'b3bc2fcf-e9dc-4a1b-a32d-98920cb78c75',
    'Star Wars: Episode VI - Return of the Jedi',
    'The final battle of the original trilogy between the Rebel Alliance and the Empire.',
    8.3,
    NOW(),
    NOW()
  ),
  (
    '800dba96-d0c7-4a43-8304-d0eebba039cb',
    'Star Wars: Episode VII - The Force Awakens',
    'Thirty years after the Empire, a new threat rises and a new hero discovers a connection to the Force.',
    7.9,
    NOW(),
    NOW()
  ),
  (
    '1c62b186-7eaa-4a9f-af65-7166c15f5594',
    'Star Wars: Episode I - The Phantom Menace',
    'The Trade Federation threatens Naboo while a young boy is discovered with a powerful destiny.',
    6.5,
    NOW(),
    NOW()
  ),
  (
    '651a6b9c-72f4-4c5c-84ef-d0285ac91518',
    'Star Wars: Episode III - Revenge of the Sith',
    'The fall of Anakin Skywalker and the rise of Darth Vader during the end of the Clone Wars.',
    7.5,
    NOW(),
    NOW()
  ),
  (
    '42b2d3e9-5cca-4e0d-a0e8-3225a491376f',
    'Star Wars: Episode II - Attack of the Clones',
    'The Republic faces a separatist crisis while Anakin and Padme grow closer.',
    6.5,
    NOW(),
    NOW()
  ),
  (
    'e7d254c9-22e2-40b7-9280-f9b773f19bab',
    'Star Trek',
    'A reboot of the Star Trek universe following a young James Kirk and the crew of the Enterprise.',
    7.9,
    NOW(),
    NOW()
  ),
  (
    '3abd0254-e3eb-4b4c-8b8d-b8117b5cb3e0',
    'Star Wars: Episode VIII - The Last Jedi',
    'Rey trains with Luke Skywalker while the Resistance struggles to survive against the First Order.',
    7.0,
    NOW(),
    NOW()
  ),
  (
    'ea7138b8-157f-4e5d-b53d-8b64c63d17cd',
    'Rogue One: A Star Wars Story',
    'A desperate mission to steal the Death Star plans before the events of A New Hope.',
    7.8,
    NOW(),
    NOW()
  );
