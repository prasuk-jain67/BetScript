import traceback
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import get_user_model, logout, authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect ,get_object_or_404
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
import re
from .models import Bot, Match, TestBot, TestMatch
from .utils import play_match,play_test_match
from .tournament_runner import run_tournament

User = get_user_model()


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirmPassword = request.POST.get('confirmPassword')

        if password != confirmPassword:
            messages.error(request, "Passwords do not match!")
            return redirect('/login/')

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return redirect('/login/')
        if not re.search(r'\d', password):
            messages.error(request, "Password must contain at least one number.")
            return redirect('/login/')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            messages.error(request, "Password must contain at least one special character.")
            return redirect('/login/')
        if not re.search(r'[A-Z]', password):
            messages.error(request, "Password must contain at least one uppercase letter.")
            return redirect('/login/')

        if User.objects.filter(username=username).exists():
            messages.info(request, "Username already taken!")
            return redirect('/login/')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.save()

        messages.info(request, "Account created Successfully!")
        return redirect('/login/')

    return render(request, 'login.html')

def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not User.objects.filter(username=username).exists():
            messages.error(request, 'Invalid Username')
            return redirect('/login/')
        user = authenticate(username=username, password=password)

        if user is None:
            messages.error(request, "Invalid Password")
            return redirect('/login/')
        else:
            login(request, user)
            return redirect('/')

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('home')

def home(request):
    user_logged_in = request.user.is_authenticated
    return render(request, 'home.html', {'user_logged_in': user_logged_in})


@login_required
def deploy_bot(request):
    return render(request, 'deploy.html')

def contact_us(request):
    return render(request, 'contact.html')

def documentation(request):
    return render(request, 'documentation.html')


@login_required
def upload_bot(request):
    user = request.user
    bot_name = request.POST.get('bot_name')
    bot_file_path = request.POST.get('bot_file_path')
    if Bot.objects.filter(user=user).count()>1:
        messages.error(request, "You can only upload 1 bot.")
        return redirect('deploy_bot') 
    
    if Bot.objects.filter(name=bot_name).exists():
        messages.error(request, "Bot name already taken!")
        

    try:
        with open(bot_file_path, 'r') as file:
            bot_file = file.read()

    except FileNotFoundError:
        messages.error(request, f"The file at {bot_file_path} was not found.")
        return redirect('deploy_bot')

    try:
        Bot.objects.create(user=user, name=bot_name, file=bot_file, path=bot_file_path)
        
        messages.success(request, f"Bot '{bot_name}' uploaded successfully!")
    
    except Exception as e:
        traceback.print_exc()
        messages.error(request, "An error occurred while uploading the bot.")
        return redirect('deploy_bot')

    return redirect('deploy_bot')

@login_required
@transaction.atomic
def test_run(request):
    try:
        user = request.user
        bot_name = request.POST.get('name').strip()
        bot_file = request.FILES['file']

        if not bot_name:
            messages.error(request, "Bot name cannot be empty")
            return redirect('/deploy_bot/')

        if Bot.objects.filter(name=bot_name).exists():
            messages.info(request, "Bot name already taken!")
            return redirect('/deploy_bot/')

        try:
            new_test_bot = TestBot.objects.create(
                user=user,
                name=bot_name,
                file=bot_file
            )
        except (IOError, ValidationError) as e:
            messages.error(request, f"Error saving bot file: {str(e)}")
            return redirect('/deploy_bot/')

        import glob
        import os
        
        bot_files = glob.glob('bots/*.py')
        available_opponents = []
        test_bot_objects = {} # Map name to TestBot object for quick lookup/creation

        for file_path in bot_files:
            filename = os.path.basename(file_path)
            if filename in ['base.py', '__init__.py']:
                continue
            
            name = filename.replace('.py', '') 
            
            try:
                bot, _ = TestBot.objects.get_or_create(
                    user=user,
                    name=name,
                    defaults={'file': file_path}
                )
                available_opponents.append({'name': name, 'path': file_path})
                test_bot_objects[name] = bot
            except Exception as e:
                continue

        try:
            best_match, worst_match, metadata = run_tournament(new_test_bot, available_opponents, iterations=10)
            
            if not best_match or not worst_match:
                 messages.error(request, "Error executing tournament")
                 return redirect('/deploy_bot/')
                 
        except Exception as e:
            messages.error(request, f"Error executing match: {str(e)}")
            return redirect('/deploy_bot/')

        def get_match_players(match_info):
            players = [new_test_bot]
            for opp_name in match_info['opponent_names']:
                if opp_name in test_bot_objects:
                    players.append(test_bot_objects[opp_name])
            return players

        try:
            best_players = get_match_players(best_match)
            best_test_match = TestMatch.objects.create(
                winner=best_match['winner'],
                rounds_data=best_match['rounds_data'],
                player_order=[b.id for b in best_players]
            )
            best_test_match.players.set(best_players)
            
            worst_players = get_match_players(worst_match)
            worst_test_match = TestMatch.objects.create(
                winner=worst_match['winner'],
                rounds_data=worst_match['rounds_data'],
                player_order=[b.id for b in worst_players]
            )
            worst_test_match.players.set(worst_players)

        except Exception as e:
            messages.error(request, f"Error saving match results: {str(e)}")
            return redirect('/deploy_bot/')

        # Prepare results
        results = {
            'best_match_id': best_test_match.id,
            'worst_match_id': worst_test_match.id,
            'opponents': [op['name'] for op in available_opponents], # List all available for info
            'best_winner': best_match['winner'],
            'worst_winner': worst_match['winner'],
            'metadata': metadata
        }

        return render(request, 'test_run_Response.html', {
            'results': results,
            'testbot': new_test_bot
        })

    except Exception as e:
        messages.error(request, f"Unexpected error occurred: {str(e)}")
        return redirect('/deploy_bot/')
    
@login_required
def test_replay(request, match_id):
    match = get_object_or_404(TestMatch, id=match_id)
    ordered_players = [TestBot.objects.get(id=bot_id).name for bot_id in match.player_order]
    
    return render(request, 'test_multigame.html', {
        'rounds_data': match.rounds_data,
        'players': ordered_players,  # Correct order
        'match': match,
        'bot_id': match.bot1.id
    })



def test_match_results(request, match_id):
    try:
        # Get match with error handling for invalid ID
        match = get_object_or_404(TestMatch, id=match_id)
        
        # Get user's bot in the match with permission check
        testbot = match.players.filter(user=request.user).first()
        if not testbot:
            messages.error(request, "You don't have permission to view this match")
            return redirect('deploy_bot')  # Redirect to appropriate page

        # Validate match data integrity
        if not all(hasattr(match, attr) for attr in ['winner', 'played_at', 'rounds_data']):
            messages.error(request, "Invalid match data structure")
            return redirect('deploy_bot')

        # Safely prepare opponents list
        try:
            opponents = [player.name for player in match.players.all() if player.id != testbot.id]
        except AttributeError as e:
            messages.error(request, f"Error processing player data: {str(e)}")
            return redirect('deploy_bot')
        
        # Validate rounds data format
        if not isinstance(match.rounds_data, list):
            messages.error(request, "Invalid round data format")
            return redirect('deploy_bot')

        # Prepare results with error handling
        try:
            results = [{
                'match': match,
                'opponents': opponents,
                'winner': match.winner,
                'played_at': match.played_at,
                'rounds_data': match.rounds_data,
            }]
        except KeyError as e:
            messages.error(request, f"Missing key in match data: {str(e)}")
            return redirect('deploy_bot')

        context = {
            'testbot': testbot,
            'results': results,
        }

        return render(request, 'test_run_Response2.html', context)

    except PermissionDenied:
        messages.error(request, "You don't have permission to access this resource")
        return redirect('login')
        
    except ObjectDoesNotExist as e:
        messages.error(request, "Requested resource no longer exists")
        return redirect('deploy_bot')
        
    except Exception as e:
        # Log the exception here (consider adding logging)
        messages.error(request, "An unexpected error occurred")
        return redirect('deploy_bot')


@login_required
def admin_panel(request):
    if not request.user.is_staff and not request.user.is_superuser:
        return redirect('home')

    if request.method == 'POST':
        selected_bot_ids = request.POST.getlist('bots')
        selected_bots = Bot.objects.filter(id__in=selected_bot_ids)
        
        if len(selected_bots) < 2:
            messages.error(request, "Please select at least 2 bots.")
            return redirect('admin_panel')
        if len(selected_bots) > 6:
            messages.error(request, "Maximum 6 bots allowed per match.")
            return redirect('admin_panel')

        bot_paths = [bot.path for bot in selected_bots]

        result = play_match(bot_paths,selected_bots)
        
        if isinstance(result[0], list):
            for error in result[0]:
                messages.error(request, error)
            return redirect('admin_panel')
        
        winner_name,rounds_data = result

        if(rounds_data==None):
            return JsonResponse({"Error":winner_name})

        try:            
            match = Match.objects.create(
                winner=winner_name,
                rounds_data=rounds_data
            )
            match.players.add(*selected_bots)
        
        except Exception as e:
            messages.error(request, f"Error saving match: {str(e)}")

        return redirect('admin_panel')

    all_bots = Bot.objects.all().order_by('name')
    recent_matches = Match.objects.all().order_by('-played_at')[:10]

    return render(request, 'admin_panel.html', {
        'all_bots': all_bots,
        'recent_matches': recent_matches,
        'max_bots': range(2, 7)
    })

@login_required
def replay(request, match_id):
    if not request.user.is_staff and not request.user.is_superuser:
        return redirect('')
    
    match = get_object_or_404(Match,id=match_id)
    players = [bot.name for bot in match.players.all()]
    return render(request, 'multigame.html',{
        'rounds_data': match.rounds_data,
        'players': players,
    })
