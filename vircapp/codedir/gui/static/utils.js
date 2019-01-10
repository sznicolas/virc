var ticker_stats = {}; //received by sse tickerhandler(), used in fill_ticker_details()
var tickerbg = "#2f485a"; //TODO: automaite get bg color to store it

// sse alerts
function flashhandler(event) {
	html = "<div class='alert alert-" + event.type +
		" alert-dismissible' role='alert' data-dismiss='alert' data-toggle='tooltip' title='Click to close'>" +
		event.data + "</div>";
	$(html).prependTo('#flash');
}

// new sse alerts
function messagehandler(event) {
	 var obj = JSON.parse(event.data);
	html = "<div class='alert alert-" + obj.level +
		" alert-dismissible' role='alert' data-dismiss='alert' data-toggle='tooltip' title='Click to close'>" +
		obj.message + "</div>";
	$(html).prependTo('#flash');
}

// updates data in the ticker panel
function tickerhandler(event) {
	data = JSON.parse(event.data);
	ticker_stats[data.ticker.pair] = data;

	pticker = '#panel-ticker-' + data.ticker.pair;
	ptprice = pticker + " .panel-ticker-price";
	ptoc    = pticker + " .panel-ticker-oc";
	oldprice = $(ptprice).text();
	if (oldprice < data.ticker.price) {
		hgstyle = {"background-color": "darkGreen"};
		bgcol = "darkGreen";
	} else {
		hgstyle = {"background-color": "darkRed"};
		bgcol = "darkRed";
	}
	nstyle = {"background-color": "#2f485a"};
	$(pticker).css("background-color", bgcol);
	$(pticker).fadeOut("slow");
	$(ptprice).text(data.ticker.price);
	$(pticker + " .panel-ticker-oc").text(Number((data.ticker.oc).toFixed(2)) + "%"); 
	if ( data.ticker.oc > 0){
		$(ptoc).css("color", "lawnGreen");
		//$("<i class='fa fa-arrow-up'></i>").appendTo(ptoc) ;
	} else if (data.ticker.oc < 0) {
		$(ptoc).css("color", "red");
		//$("<i class='fa fa-arrow-dowen'></i>").appendTo(ptoc) ;
		//$(ptoc).addClass("fa fa-arrow-down");
	}
	if ($("#ticker-detail-pair").text() == data.ticker.pair){
		fill_ticker_details(data.ticker.pair);
	}
	$(pticker).fadeIn("fast")
	setTimeout(function() { $(pticker).css(nstyle) ; }, 2000);
}

// opens the detailled ticker panel
function open_ticker_details(pair) {
	$("#ticker-panel").addClass("ticker-panel-open");
	$("#ticker-panel").removeClass("ticker-panel-mini");
	$("#ticker-details").removeClass("d-none");
	fill_ticker_details(pair);
}

function fill_ticker_details(pair){
	var stats = ticker_stats[pair];
	var bgstyle;
	$("#ticker-detail-tbody").empty();
	$("#ticker-detail-pair").text(stats.ticker.pair);
	for ( k in stats) { 
		if ( k == "ticker")   { continue; }
		if (stats[k].oc > 0) {
				bgstyle = "background-color: darkGreen;";
		} else if (stats[k].oc < 0) {
				bgstyle = "background-color: darkRed;";
		}
		html = "<tr style='" + bgstyle + "'><th>" + stats[k].title + "</th><td>" + stats[k].low +
				"</td><td>" + stats[k].high + "</td><td>" + stats[k].volume.toFixed(2) + 
				"</td><td>" + stats[k].oc.toFixed(2) + "%</td></tr>";
		$(html).appendTo('#ticker-detail-tbody');
	}
}

function close_ticker_details(){
	$("#ticker-panel").removeClass("ticker-panel-open");
	$("#ticker-panel").addClass("ticker-panel-mini");
	$("#ticker-details").addClass("d-none");
	$("#ticker-detail-pair").text("");
}

$(window).on('beforeunload', function(){
   		flashsse.close();
		tickersse.close();
		vircpubsse.close();
});

// Confirm with 'confirmation' class
$('.confirmation').on('click', function () {
	return confirm('Are you sure?');
});
