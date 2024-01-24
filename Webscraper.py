from playwright.sync_api import Page, expect
from playwright.sync_api import sync_playwright
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import sqlite3
import pandas as pd



def scrape(page: Page, cursor):
    team = input("Input team name: ")
    website = "https://www.basketball-reference.com/"
    navigate_with_retry(page, website)
    input_field = page.locator('input[tabindex="1"][type="search"]')
    input_field.fill(team)

    teampage = page.locator('//*[@id="header"]/div[3]/form/div/div/div/div[1]/div[2]/div/div/span[2]')
    teampage.click()

    teamurl = page.url
    teamurl = teamurl + '2024.html'
    navigate_with_retry(page, teamurl)

    rowCount = page.locator('//*[@id="roster"]/tbody').locator('tr').count()
    i = 1
    baseurl = page.url
    while i <= rowCount:
        getPlayerStats(page, '//*[@id="roster"]/tbody/tr[' + str(i) + ']/td[1]/a', baseurl, cursor)
        i += 1
    

def getPlayerStats(page: Page, xpath, baseurl, cursor):
    element_xpath = '//*[@id="modal-container"]' #Path for sign up pop up
    modal_element = page.locator(element_xpath)

    is_visible = modal_element.is_visible()
    if(is_visible): #if is on screen, reload page to get rid of
        print('element visible')
        navigate_with_retry(page, page.url)

    button = page.locator(xpath)
    button.click()

    url = page.url.rstrip('.html')
    new_url = url + '/gamelog/2024'
    navigate_with_retry(page, new_url)

    try:
        name = page.locator('//*[@id="meta"]/div[2]/h1/span').text_content()
    except PlaywrightTimeoutError:
        name = page.locator('//*[@id="meta"]/div/h1/span').text_content()
    if "2023-24 Game Log" in name:
        name = name.replace("2023-24 Game Log", "").strip()    


    numGames = page.locator('//*[@id="pgl_basic"]/tbody').locator('tr').count()
    i = 0
    print(name)
    while i < numGames:
        inactive = False
        page.on("dialog", on_dialog)
        try:
            element = page.locator(f'[data-row="{i}"]')
            date = element.locator('[data-stat="date_game"]').text_content()
            if(date == "Date"):
                i += 1
                continue
            team = element.locator('[data-stat="team_id"]').text_content()
            gameLocation = element.locator('[data-stat="game_location"]').text_content()
            opposition = element.locator('[data-stat="opp_id"]').text_content()
            game_result = element.locator('[data-stat="game_result"]').text_content()
            if(element.locator('[data-stat="reason"]')).is_visible(): #check to see if player was out
                inactive = True
            else:
                minutes = element.locator('[data-stat="mp"]').text_content()
                field_goal_percent = element.locator('[data-stat="fg_pct"]').text_content()
                three_point_percent = element.locator('[data-stat="fg3_pct"]').text_content()
                total_rebounds = element.locator('[data-stat="trb"]').text_content()
                assists = element.locator('[data-stat="ast"]').text_content()
                steals = element.locator('[data-stat="stl"]').text_content()
                blocks = element.locator('[data-stat="blk"]').text_content()
                points = element.locator('[data-stat="pts"]').text_content()
                plus_minus = element.locator('[data-stat="plus_minus"]').text_content()
                plus_minus = plus_minus.replace("+", '')
        except PlaywrightTimeoutError:
            print("timeout error")

        i += 1
        if(inactive == True):
            cursor.execute("""
                          INSERT INTO nba_stats (Name, Date, Team, Game_Location, Opposing_Team, Game_Result)
                          VALUES (?, ?, ?, ?, ?, ?)
            """, (name, date, team, gameLocation, opposition, game_result))
        else:
            cursor.execute("""
                          INSERT INTO nba_stats (Name, Date, Team, Game_Location, Opposing_Team, Game_Result, Minutes, FGPercent, TPPercent, Rebounds, Assists, Steals, Blocks, Points, PlusMinus)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, date, team, gameLocation, opposition, game_result, minutes, field_goal_percent, three_point_percent, total_rebounds, assists, steals, blocks, points, plus_minus)) 

    print("done with " + name)
    navigate_with_retry(page, baseurl)


def navigate_with_retry(page, url):
    while True:
        try:
            page.goto(url, timeout=30000) 
            return  # return if successful loading
        except PlaywrightTimeoutError:
            print(f"Timeout error. Retrying...")
         

# Set up event listener to automatically dismiss dialogs
def on_dialog(dialog):
    print(f'Dismissing dialog: {dialog.message()}')
    dialog.dismiss()



def main():
    conn = sqlite3.connect('nba_stats.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS nba_stats(Name, Date, Team, Game_Location, Opposing_Team, Game_Result, Minutes, FGPercent, TPPercent, Rebounds, Assists, Steals, Blocks, Points, PlusMinus)")

    new_team = input("Press 1 to enter a new team, press 2 to view data: ")
    if(new_team == '1'):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            scrape(page, cursor)
            browser.close()
    else:
        query = "SELECT Name, Team, Points, Rebounds, Assists, Date, PlusMinus FROM nba_stats"
        df = pd.read_sql_query(query, conn)
        df = df.dropna()
        df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')    #swap format of date
        df['BackToBack'] = df.groupby('Team')['Date'].diff().dt.days == 1
        # Convert 'PlusMinus' column to numeric, handling errors by coercing them to NaN
        df['PlusMinus'] = pd.to_numeric(df['PlusMinus'], errors='coerce')

        # Filter rows where 'BackToBack' is True
        back_to_back_entries = df[df['BackToBack']].groupby('Name')
        non_back_to_back_games = df[~df['BackToBack']].groupby('Name')


        # Calculate the average of 'PlusMinus' for back-to-back games
        averageb2b = back_to_back_entries['PlusMinus'].mean()
        averagenonb2b = non_back_to_back_games['PlusMinus'].mean()

        print("Average PlusMinus for Back-to-Back Games:", averageb2b)
        print("Average PlusMinus for non Back-to-Back Games:", averagenonb2b)


  
        
    conn.commit()
    conn.close()    




main()